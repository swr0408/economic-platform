"""
NZ 貿易収支サービス

指標:
- Exports (輸出額): 10億NZD
- Imports (輸入額): 10億NZD
- Trade Balance (貿易収支): 10億NZD

データソース:
- Stats NZ Overseas Merchandise Trade - Table 1.01
- 月次リリースExcelをダウンロードして解析
- 各Excelには25ヶ月分の月次データが含まれる
- 複数のExcelファイルを組み合わせて長期時系列を構築

取得戦略:
1. 最新リリースページから最新ExcelのURLを発見
2. 年末Excelファイル（Dec各年）で過去データを補完
3. FMP DBから最新データで補完

発表スケジュール:
- 月次（前月分を約3週間後に発表）
- FMPイベント: "Balance of Trade"

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import json
import logging
import re
import html
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd
import io

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_trade_balance_cache.json"

MONTH_NAMES_CAP = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}
MONTH_ABBREV = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# 過去データ取得に使う年末ファイルのリスト（古い順）
HISTORICAL_FILES = [
    # (表示月名, 年, ファイルスラグ)
    ("December", "2020", "december-2020"),
    ("December", "2021", "december-2021"),
    ("December", "2022", "december-2022"),
    ("December", "2023", "december-2023"),
    ("December", "2024", "December-2024"),
]


def _build_excel_url(month_cap: str, year: str, slug: str) -> str:
    """Stats NZ merchandise trade Excel URLを生成"""
    return (
        f"https://www.stats.govt.nz/assets/Uploads/Overseas-merchandise-trade/"
        f"Overseas-merchandise-trade-{month_cap}-{year}/Download-data/"
        f"overseas-merchandise-trade-{slug}.xlsx"
    )


def _discover_latest_excel_url() -> Optional[str]:
    """最新リリースページをスクレイピングして最新ExcelのURLを発見"""
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})

        # リリースページ一覧から最新を取得
        # まず最新の数ヶ月を試す
        now = datetime.now(JST)
        for months_ago in range(0, 4):
            month = now.month - months_ago
            year = now.year
            while month <= 0:
                month += 12
                year -= 1

            month_cap = MONTH_NAMES_CAP[month]
            release_url = (
                f"https://www.stats.govt.nz/information-releases/"
                f"overseas-merchandise-trade-{month_cap.lower()}-{year}"
            )
            try:
                resp = session.get(release_url, timeout=30)
                if resp.status_code != 200:
                    continue

                text = html.unescape(resp.text).replace("\\/", "/")
                # Excelファイルへのリンクを探す
                links = re.findall(
                    r"/assets/Uploads/Overseas-merchandise-trade/"
                    r"[^\"\'<>\s]+\.xlsx",
                    text,
                )
                # メインのデータファイル（revisions-to-previouslyを除く）
                for link in links:
                    if "revisions" not in link.lower() and "visio" not in link.lower():
                        url = f"https://www.stats.govt.nz{link}"
                        logger.info(f"[NzTrade] Discovered latest Excel URL: {url}")
                        return url

            except Exception as e:
                logger.warning(f"[NzTrade] Error checking {month_cap} {year}: {e}")
                continue

        return None
    except Exception as e:
        logger.error(f"[NzTrade] Error discovering latest URL: {e}")
        return None


def _detect_column_indices(df: pd.DataFrame) -> tuple:
    """
    ヘッダー行を解析して輸出・輸入・貿易収支の列インデックスを返す

    Returns:
        (exports_col, imports_col, balance_col)
    """
    exports_col = None
    imports_col = None
    balance_col = None

    # ヘッダー行を検索（'Exports'と'Imports'を含む行を探す）
    for i in range(min(15, df.shape[0])):
        row = df.iloc[i]
        found_exports = False
        for j in range(df.shape[1]):
            cell = str(row[j]) if pd.notna(row[j]) else ""
            if "Exports" in cell and exports_col is None:
                exports_col = j
                found_exports = True
            elif "Imports\n(cif)" in cell and imports_col is None and found_exports:
                imports_col = j
            elif "Trade balance" in cell and balance_col is None:
                balance_col = j

        if exports_col is not None and imports_col is not None and balance_col is not None:
            break

    # フォールバック: デフォルト列（January 2026等の新フォーマット）
    if exports_col is None:
        exports_col = 3
    if imports_col is None:
        imports_col = 5
    if balance_col is None:
        balance_col = 7

    return (exports_col, imports_col, balance_col)


def _parse_monthly_data(content: bytes) -> List[Dict[str, Any]]:
    """Table 1.01の月次データを解析して返す"""
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name="Table 1.01", header=None)

        # 列インデックスを動的に検出
        exports_col, imports_col, balance_col = _detect_column_indices(df)
        logger.info(f"[NzTrade] Column indices: exports={exports_col}, imports={imports_col}, balance={balance_col}")

        records = []
        current_year = None
        in_monthly_section = False

        for i in range(df.shape[0]):
            row = df.iloc[i]

            # セクション判定
            col0 = str(row[0]).strip() if pd.notna(row[0]) else ""

            if col0 == "Month":
                in_monthly_section = True
                continue

            if not in_monthly_section:
                continue

            # 年の取得
            if col0.isdigit():
                current_year = int(col0)

            # 月データの取得
            month_val = str(row[1]).strip() if pd.notna(row[1]) else ""
            if month_val not in MONTH_ABBREV:
                continue
            if current_year is None:
                continue

            month_num = MONTH_ABBREV[month_val]
            date_str = f"{current_year}-{month_num:02d}-01"

            # 各列から値を取得 (百万NZD → 十億NZD変換)
            exports_m = float(row[exports_col]) if exports_col < df.shape[1] and pd.notna(row[exports_col]) else None
            imports_m = float(row[imports_col]) if imports_col < df.shape[1] and pd.notna(row[imports_col]) else None
            balance_m = float(row[balance_col]) if balance_col < df.shape[1] and pd.notna(row[balance_col]) else None

            # 輸入額の簡単な妥当性チェック（前年比%の値は通常-50〜+50の範囲）
            # 輸入額は通常3〜10十億NZD程度（3000〜10000百万NZD）
            if imports_m is not None and abs(imports_m) < 100:
                # 異常に小さい値は前年比%と誤認識している可能性 → スキップ
                imports_m = None
                balance_m = None

            records.append({
                "date": date_str,
                "exports": round(exports_m / 1000, 3) if exports_m is not None else None,
                "imports": round(imports_m / 1000, 3) if imports_m is not None else None,
                "balance": round(balance_m / 1000, 3) if balance_m is not None else None,
            })

        return records
    except Exception as e:
        logger.error(f"[NzTrade] Error parsing Excel: {e}")
        return []


def _download_and_parse(url: str) -> List[Dict[str, Any]]:
    """URLからExcelをダウンロードして解析"""
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        resp = session.get(url, timeout=60)
        if resp.status_code == 200 and len(resp.content) > 50000:
            return _parse_monthly_data(resp.content)
        else:
            logger.warning(f"[NzTrade] Failed to download {url}: {resp.status_code}")
            return []
    except Exception as e:
        logger.warning(f"[NzTrade] Error downloading {url}: {e}")
        return []


def _merge_records(all_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """複数ファイルからのレコードをマージ（重複除去・古い優先→新しい上書き）"""
    merged: Dict[str, Dict[str, Any]] = {}
    for rec in all_records:
        date = rec["date"]
        # 後から来るデータ（新しいファイル）で上書き
        merged[date] = rec
    return sorted(merged.values(), key=lambda x: x["date"])



def _get_next_release() -> Optional[Dict[str, Any]]:
    """次回発表日をFMPから取得"""
    try:
        from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern
        return get_next_release_by_pattern("Balance of Trade", country="NZ")
    except Exception as e:
        logger.warning(f"[NzTrade] Error getting next release: {e}")
        return None


class NzTradeBalanceService:
    """NZ 貿易収支サービス"""

    DATA_CACHE_KEY = "newzealand:nz_trade_balance:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ 貿易収支データを取得"""

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データ取得
        result = self._load_all_data()
        next_release = _get_next_release()

        if result:
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Stats NZ",
                    "indicator": "Overseas Merchandise Trade",
                    "description": "NZ 貿易収支（輸出入額・収支）",
                    "unit": "10億NZD",
                    "frequency": "monthly",
                    "table": "Table 1.01 - Actual values",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "stats_nz",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """1日1回更新"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() > 86400
        except Exception:
            return True

    def _load_all_data(self) -> List[Dict[str, Any]]:
        """全データを取得（過去ファイル + 最新ファイル）"""
        all_records = []

        # 1. 過去の年末ファイルを取得
        for month_cap, year, slug in HISTORICAL_FILES:
            url = _build_excel_url(month_cap, year, slug)
            records = _download_and_parse(url)
            if records:
                logger.info(f"[NzTrade] Loaded {len(records)} records from {month_cap} {year}")
                all_records.extend(records)
            else:
                logger.warning(f"[NzTrade] No data from {month_cap} {year}")

        # 2. 最新ファイルを動的に発見してダウンロード
        latest_url = _discover_latest_excel_url()
        if latest_url:
            latest_records = _download_and_parse(latest_url)
            if latest_records:
                logger.info(f"[NzTrade] Loaded {len(latest_records)} records from latest release")
                all_records.extend(latest_records)

        if not all_records:
            logger.error("[NzTrade] No data from any Stats NZ source")
            return []

        # 3. マージ（重複除去）
        merged = _merge_records(all_records)
        logger.info(f"[NzTrade] Total merged records: {len(merged)}")

        if merged:
            latest = merged[-1]
            logger.info(f"[NzTrade] Latest: {latest['date']}, balance={latest.get('balance')}")

        return merged

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュに保存"""
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzTrade] Error saving file cache: {e}")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュから読み込み"""
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"[NzTrade] Error loading file cache: {e}")
        return None


# シングルトン
nz_trade_balance_service = NzTradeBalanceService()
