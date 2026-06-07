"""
中古車価格 サービス（FRED + Manheim Used Vehicle Value Index）

2系列を統合した中古車価格の前年比表示:
- fred_yoy: FRED CPI Used Cars and Trucks YoY（CUSR0000SETA02）
  CPIと同タイミング発表（米国CPI発表時）
- manheim_yoy: Manheim Used Vehicle Value Index YoY
  毎月第5営業日以降に Cox Automotive のサイトで発表

データソース:
- FRED: https://fred.stlouisfed.org/series/CUSR0000SETA02
- Manheim: https://www.coxautoinc.com/insights/?insight_series=manheim-used-vehicle-index

更新スケジュール:
- FRED: CPI発表時刻ベース（econalpha_id="us_cpi"）
- Manheim: 毎月5日以降1日1回チェック、対象月データ取得後は次月5日までスキップ
  （詳細は backend/scheduler/manheim_used_vehicle_scheduler.py）
"""
import io
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)
from services.usa.fred_utils import fetch_fred_series, calculate_changes


JST = ZoneInfo("Asia/Tokyo")

FRED_SERIES_ID = "CUSR0000SETA02"
COX_BASE_URL = "https://www.coxautoinc.com"
MANHEIM_LIST_URL = (
    "https://www.coxautoinc.com/insights/?insight_series=manheim-used-vehicle-index"
)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "used_car_prices_cache.json"

# Manheim取得の最小再試行間隔（24時間 = 1日1回）
MANHEIM_RETRY_INTERVAL_SECONDS = 24 * 60 * 60
# Manheim発表が期待される最早日（毎月の日付）
MANHEIM_EXPECTED_DAY_OF_MONTH = 5


class UsedCarPricesService:
    """中古車価格サービス（FRED + Manheim）"""

    DATA_CACHE_KEY = "inflation:used_car_prices:data"
    ECONALPHA_ID = "us_cpi"  # FRED側のスケジュール判定に使用

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        中古車価格データを取得（FRED + Manheim 統合）

        Returns:
            {
                "data": [{"date", "fred_yoy", "manheim_yoy"}, ...],
                "latest": {...},
                "next_release": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        cached = redis_client.get(self.DATA_CACHE_KEY)
        if cached is None:
            cached = self._load_file_cache()

        # 各系列の更新判定
        needs_fred = force_refresh or self._should_refresh_fred(cached)
        needs_manheim = force_refresh or self._should_refresh_manheim(cached)

        if not needs_fred and not needs_manheim and cached:
            return {
                "data": cached.get("data", []),
                "latest": cached.get("latest"),
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": True,
                "source": "cache",
                "last_updated": cached.get("last_updated"),
            }

        # 既存キャッシュから引き継ぎ
        fred_data = cached.get("fred_data", []) if cached else []
        manheim_data = cached.get("manheim_data", []) if cached else []
        fred_last_updated = cached.get("fred_last_updated") if cached else None
        manheim_last_attempted = (
            cached.get("manheim_last_attempted") if cached else None
        )

        # 必要な系列のみフェッチ
        if needs_fred:
            new_fred = self._fetch_fred()
            if new_fred:
                fred_data = new_fred
                fred_last_updated = datetime.now(JST).isoformat()

        if needs_manheim:
            new_manheim = self._fetch_manheim()
            manheim_last_attempted = datetime.now(JST).isoformat()
            if new_manheim:
                manheim_data = new_manheim

        # マージ
        merged = self._merge(fred_data, manheim_data)
        latest = merged[-1] if merged else None

        cache_payload = {
            "data": merged,
            "latest": latest,
            "fred_data": fred_data,
            "manheim_data": manheim_data,
            "fred_latest_date": fred_data[-1]["date"] if fred_data else None,
            "manheim_latest_date": manheim_data[-1]["date"] if manheim_data else None,
            "fred_last_updated": fred_last_updated,
            "manheim_last_attempted": manheim_last_attempted,
            "last_updated": datetime.now(JST).isoformat(),
        }
        redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "data": merged,
            "latest": latest,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "cached": False,
            "source": "api",
            "last_updated": cache_payload["last_updated"],
        }

    # ---------------------------------------------------------------
    # 更新判定
    # ---------------------------------------------------------------

    def _should_refresh_fred(self, cache_payload: Optional[Dict[str, Any]]) -> bool:
        """FREDの更新判定: CPI発表ベース"""
        if not cache_payload:
            return True
        fred_last_updated = cache_payload.get("fred_last_updated")
        if not fred_last_updated:
            return True
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, fred_last_updated)

    def _should_refresh_manheim(self, cache_payload: Optional[Dict[str, Any]]) -> bool:
        """
        Manheimの更新判定:
        - 毎月5日未満: スキップ（発表前）
        - 対象月（先月）データを既に保持: スキップ（次月5日までスキップ）
        - 最終試行から24時間未満: スキップ（1日1回）
        - 上記以外: 更新
        """
        if not cache_payload:
            return True

        now = datetime.now(JST)
        today = now.date()

        # 毎月5日未満は発表前の可能性 → スキップ
        if today.day < MANHEIM_EXPECTED_DAY_OF_MONTH:
            return False

        # 対象月 = 先月（PCEと同じく前月分が公表される）
        target_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

        # 既に対象月データを保持していれば次月5日までスキップ
        manheim_latest = cache_payload.get("manheim_latest_date")
        if manheim_latest:
            try:
                last_dt = datetime.strptime(manheim_latest, "%Y-%m-%d").date()
                if last_dt >= target_month_start:
                    return False
            except ValueError:
                pass

        # 最終試行から24時間未満ならスキップ（1日1回）
        last_attempted = cache_payload.get("manheim_last_attempted")
        if last_attempted:
            try:
                last_dt = datetime.fromisoformat(last_attempted)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=JST)
                elapsed = (now - last_dt).total_seconds()
                if elapsed < MANHEIM_RETRY_INTERVAL_SECONDS:
                    return False
            except (ValueError, TypeError):
                pass

        return True

    # ---------------------------------------------------------------
    # データ取得
    # ---------------------------------------------------------------

    def _fetch_fred(self) -> List[Dict[str, Any]]:
        """FRED CUSR0000SETA02 から取得し前年比を算出"""
        try:
            print(f"[used_car_prices] Fetching FRED {FRED_SERIES_ID}...")
            raw = fetch_fred_series(FRED_SERIES_ID, start_date="1995-01-01")
            if not raw:
                print("[used_car_prices] FRED returned empty")
                return []
            changes = calculate_changes(raw, include_value=True)
            # YoY が None のレコードは除外
            result = [
                {"date": item["date"], "yoy": item["yoy"]}
                for item in changes
                if item.get("yoy") is not None
            ]
            print(f"[used_car_prices] FRED fetched {len(result)} YoY records")
            return result
        except Exception as e:
            print(f"[used_car_prices] FRED fetch error: {e}")
            return []

    def _fetch_manheim(self) -> List[Dict[str, Any]]:
        """Manheim Used Vehicle Value Index の最新Excelをスクレイピングして取得"""
        try:
            print("[used_car_prices] Fetching Manheim from Cox Automotive...")
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

            # 1. 一覧ページから最新の正式月次記事URLを抽出（Mid-月次は除外）
            article_url = self._find_latest_article_url(session)
            if not article_url:
                print("[used_car_prices] Manheim article URL not found")
                return []

            print(f"[used_car_prices] Article: {article_url}")

            # 2. 記事ページから Excel ダウンロードURLを抽出
            xlsx_url = self._find_xlsx_url(session, article_url)
            if not xlsx_url:
                print("[used_car_prices] Manheim Excel URL not found")
                return []

            print(f"[used_car_prices] Excel: {xlsx_url}")

            # 3. Excelをダウンロードしてパース
            resp = session.get(xlsx_url, timeout=60)
            resp.raise_for_status()

            result = self._parse_manheim_excel(resp.content)
            print(f"[used_car_prices] Manheim parsed {len(result)} records")
            return result
        except Exception as e:
            print(f"[used_car_prices] Manheim fetch error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _find_latest_article_url(self, session: requests.Session) -> Optional[str]:
        """Cox一覧ページから最新の正式月次記事URL（Mid-月次除外）を抽出"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print("[used_car_prices] beautifulsoup4 not installed")
            return None

        resp = session.get(MANHEIM_LIST_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for a in soup.select("a[href]"):
            href = urljoin(COX_BASE_URL, a.get("href", ""))
            text = a.get_text(" ", strip=True)
            if (
                "manheim-used-vehicle-value-index" in href
                and "trends" in href
                and "mid" not in href.lower()
                and "Mid-" not in text
            ):
                return href
        return None

    def _find_xlsx_url(
        self, session: requests.Session, article_url: str
    ) -> Optional[str]:
        """記事ページから Excel ダウンロードURLを抽出"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None

        resp = session.get(article_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for a in soup.select("a[href]"):
            href = urljoin(COX_BASE_URL, a.get("href", ""))
            text = a.get_text(" ", strip=True)
            if "Download the Data" in text or re.search(
                r"\.xlsx($|\?)", href, re.IGNORECASE
            ):
                # Manheim関連のExcelファイルに限定
                if (
                    "Manheim-Used-Vehicle-Value-Index" in href
                    or "Manheim" in href
                    or "MUVVI" in href.upper()
                    or "Download the Data" in text
                ):
                    return href
        return None

    @staticmethod
    def _parse_manheim_excel(content: bytes) -> List[Dict[str, Any]]:
        """
        Manheim Excelをパースして YoY を抽出

        DATAシート構造:
        - Col 0: Date (YYYY-MM-DD)
        - Col 1: Index (1/97 = 100)
        - Col 7: Index % YoY (小数: 0.04 = 4%)
        """
        import pandas as pd

        df = pd.read_excel(
            io.BytesIO(content), sheet_name="DATA", header=None, engine="openpyxl"
        )

        result: List[Dict[str, Any]] = []
        for idx in range(1, df.shape[0]):  # Row 0 はヘッダー
            date_val = df.iloc[idx, 0]
            yoy_val = df.iloc[idx, 7] if df.shape[1] > 7 else None

            if pd.isna(date_val) or pd.isna(yoy_val):
                continue

            try:
                date_obj = pd.to_datetime(date_val)
                # Excel上は小数（0.04）なので %換算
                yoy_pct = round(float(yoy_val) * 100, 2)
                result.append({
                    "date": date_obj.strftime("%Y-%m-%d"),
                    "yoy": yoy_pct,
                })
            except (ValueError, TypeError):
                continue

        result.sort(key=lambda x: x["date"])
        return result

    @staticmethod
    def _merge(
        fred_data: List[Dict[str, Any]], manheim_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """日付でマージ"""
        merged: Dict[str, Dict[str, Any]] = {}
        for item in fred_data:
            merged[item["date"]] = {
                "date": item["date"],
                "fred_yoy": item.get("yoy"),
                "manheim_yoy": None,
            }
        for item in manheim_data:
            date = item["date"]
            if date in merged:
                merged[date]["manheim_yoy"] = item.get("yoy")
            else:
                merged[date] = {
                    "date": date,
                    "fred_yoy": None,
                    "manheim_yoy": item.get("yoy"),
                }
        return sorted(merged.values(), key=lambda x: x["date"])

    # ---------------------------------------------------------------
    # ファイルキャッシュ
    # ---------------------------------------------------------------

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[used_car_prices] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[used_car_prices] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        cached = redis_client.get(self.DATA_CACHE_KEY)
        return {
            "indicator": "Used Car Prices",
            "source": "FRED + Manheim",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": cached is not None,
            "last_updated": cached.get("last_updated") if cached else None,
            "fred_latest_date": cached.get("fred_latest_date") if cached else None,
            "manheim_latest_date": cached.get("manheim_latest_date") if cached else None,
            "fred_last_updated": cached.get("fred_last_updated") if cached else None,
            "manheim_last_attempted": cached.get("manheim_last_attempted") if cached else None,
            "data_count": len(cached.get("data", [])) if cached else 0,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
used_car_prices_service = UsedCarPricesService()
