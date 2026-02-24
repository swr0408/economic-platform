"""
NZ消費者物価指数（CPI）サービス

指標:
- All Groups CPI（全グループCPI）- QoQ / YoY
- Tradable CPI（貿易財CPI）- QoQ / YoY
- Non-Tradable CPI（非貿易財CPI）- QoQ / YoY

データソース:
- Stats NZ Consumers Price Index
- https://www.stats.govt.nz/indicators/consumers-price-index-cpi/

取得方法:
- Stats NZ リリースページから CSV を直接ダウンロード
- index-numbers.csv から All Groups CPI (CPIQ.SE9A) を取得
- tradeables-and-non-tradeables.csv から Tradable/Non-Tradable を取得
- Index値から QoQ%, YoY% を算出

系列ID:
- CPIQ.SE9A       : All Groups CPI Index (base June 2006 qtr = 1000)
- CPIQ.SE9NS6000  : Tradable All Groups Index
- CPIQ.SE9NS6500  : Non-Tradable All Groups Index

発表スケジュール:
- 四半期ごと（FMPから次回発表日取得）

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import json
import logging
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_cpi_cache.json"

# Stats NZ CPI CSV URL パターン
QUARTER_MONTHS = {
    3: ("March", "march"),
    6: ("June", "june"),
    9: ("September", "september"),
    12: ("December", "december"),
}

# 対象系列ID
SERIES_ALL_GROUPS = "CPIQ.SE9A"
SERIES_TRADABLE = "CPIQ.SE9NS6000"
SERIES_NON_TRADABLE = "CPIQ.SE9NS6500"


def _build_csv_url(year: int, quarter_month: int, csv_type: str) -> str:
    """Stats NZ CPI CSV URLを生成

    csv_type: 'index-numbers' or 'tradeables-and-non-tradeables'
    """
    month_cap, month_lower = QUARTER_MONTHS[quarter_month]
    return (
        f"https://www.stats.govt.nz/assets/Uploads/Consumers-price-index/"
        f"Consumers-price-index-{month_cap}-{year}-quarter/Download-data/"
        f"consumers-price-index-{month_lower}-{year}-quarter-{csv_type}.csv"
    )


def _period_to_date(period_str: str) -> str:
    """Stats NZ Period (YYYY.MM) を日付文字列 (YYYY-MM-01) に変換"""
    parts = str(period_str).split(".")
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1].zfill(2)}-01"
    return str(period_str)


class NzCpiService:
    """NZ消費者物価指数（CPI）サービス"""

    DATA_CACHE_KEY = "newzealand:nz_cpi:data"

    def __init__(self):
        pass

    def get_nz_cpi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ CPIデータを取得"""

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

        # Stats NZ CSVからデータ取得
        result = self._load_from_stats_nz()
        if result:
            latest = result[-1] if result else None
            next_release = self._get_next_release()

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Stats NZ",
                    "indicator": "Consumers Price Index (CPI)",
                    "description": "NZ消費者物価指数（CPI）",
                    "unit": "Index (June 2006 qtr = 1000)",
                    "frequency": "quarterly",
                    "series_all": SERIES_ALL_GROUPS,
                    "series_tradable": SERIES_TRADABLE,
                    "series_non_tradable": SERIES_NON_TRADABLE,
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
        """キャッシュを更新すべきか判定（1日1回）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() > 86400
        except Exception:
            return True

    def _load_from_stats_nz(self) -> Optional[List[Dict[str, Any]]]:
        """Stats NZ CPI CSVからデータを取得"""
        try:
            now = datetime.now(JST)
            attempts = self._get_quarter_attempts(now.year, now.month)

            # 1. index-numbers.csv から All Groups CPI Index を取得
            df_idx = None
            for year, qm in attempts:
                url = _build_csv_url(year, qm, "index-numbers")
                print(f"[NzCPI] Trying index-numbers: {url}")
                try:
                    resp = requests.get(url, timeout=120)
                    if resp.status_code == 200 and len(resp.content) > 5000:
                        df_idx = pd.read_csv(io.StringIO(resp.text), low_memory=False)
                        month_cap, _ = QUARTER_MONTHS[qm]
                        print(f"[NzCPI] Downloaded index-numbers {month_cap} {year} ({len(resp.content)} bytes, {len(df_idx)} rows)")
                        break
                    else:
                        print(f"[NzCPI] HTTP {resp.status_code} for index-numbers {year} Q{qm // 3}")
                except Exception as e:
                    print(f"[NzCPI] Error downloading index-numbers {year} Q{qm // 3}: {e}")
                    continue

            if df_idx is None:
                print("[NzCPI] Failed to download index-numbers CSV")
                return None

            # 2. tradeables-and-non-tradeables.csv を取得
            df_tn = None
            for year, qm in attempts:
                url = _build_csv_url(year, qm, "tradeables-and-non-tradeables")
                print(f"[NzCPI] Trying tradeables: {url}")
                try:
                    resp = requests.get(url, timeout=120)
                    if resp.status_code == 200 and len(resp.content) > 5000:
                        df_tn = pd.read_csv(io.StringIO(resp.text), low_memory=False)
                        month_cap, _ = QUARTER_MONTHS[qm]
                        print(f"[NzCPI] Downloaded tradeables {month_cap} {year} ({len(resp.content)} bytes, {len(df_tn)} rows)")
                        break
                    else:
                        print(f"[NzCPI] HTTP {resp.status_code} for tradeables {year} Q{qm // 3}")
                except Exception as e:
                    print(f"[NzCPI] Error downloading tradeables {year} Q{qm // 3}: {e}")
                    continue

            # All Groups CPI Index を抽出
            all_groups = self._extract_index_series(df_idx, SERIES_ALL_GROUPS, "all")
            if not all_groups:
                print("[NzCPI] No All Groups CPI data found")
                return None

            # Tradable / Non-Tradable を抽出（任意）
            tradable = {}
            non_tradable = {}
            if df_tn is not None:
                tradable = self._extract_index_series(df_tn, SERIES_TRADABLE, "tradable")
                non_tradable = self._extract_index_series(df_tn, SERIES_NON_TRADABLE, "non_tradable")

            # マージして結果を構築
            result = self._merge_series(all_groups, tradable, non_tradable)

            if result:
                print(f"[NzCPI] Total {len(result)} records")
                print(f"[NzCPI] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[NzCPI] Latest: All={latest.get('all_qoq')}% QoQ, {latest.get('all_yoy')}% YoY")
                if latest.get("tradable_yoy") is not None:
                    print(f"[NzCPI] Tradable={latest.get('tradable_yoy')}% YoY, Non-Tradable={latest.get('non_tradable_yoy')}% YoY")

            return result

        except Exception as e:
            print(f"[NzCPI] Error loading from Stats NZ: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_index_series(
        self, df: pd.DataFrame, series_ref: str, prefix: str
    ) -> Dict[str, float]:
        """DataFrameから指定系列のIndex値をdict(date -> value)で返す"""
        subset = df[df["Series_reference"] == series_ref].copy()
        if len(subset) == 0:
            print(f"[NzCPI] Series {series_ref} not found")
            return {}

        mapping = {}
        for _, row in subset.iterrows():
            period = str(row["Period"])
            value = row["Data_value"]
            if pd.notna(value):
                date_str = _period_to_date(period)
                try:
                    mapping[date_str] = float(value)
                except (ValueError, TypeError):
                    continue

        print(f"[NzCPI] {prefix} ({series_ref}): {len(mapping)} records")
        return mapping

    def _merge_series(
        self,
        all_groups: Dict[str, float],
        tradable: Dict[str, float],
        non_tradable: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Index値からQoQ%/YoY%を算出してマージ"""
        # 日付でソート
        all_dates = sorted(all_groups.keys())

        # QoQ% / YoY% を算出するための連続データ
        all_qoq = self._compute_pct_change(all_groups, all_dates, periods=1)
        all_yoy = self._compute_pct_change(all_groups, all_dates, periods=4)
        trad_qoq = self._compute_pct_change(tradable, all_dates, periods=1)
        trad_yoy = self._compute_pct_change(tradable, all_dates, periods=4)
        ntrad_qoq = self._compute_pct_change(non_tradable, all_dates, periods=1)
        ntrad_yoy = self._compute_pct_change(non_tradable, all_dates, periods=4)

        result = []
        for date_str in all_dates:
            item: Dict[str, Any] = {"date": date_str}

            # All Groups
            item["all_qoq"] = all_qoq.get(date_str)
            item["all_yoy"] = all_yoy.get(date_str)

            # Tradable
            item["tradable_qoq"] = trad_qoq.get(date_str)
            item["tradable_yoy"] = trad_yoy.get(date_str)

            # Non-Tradable
            item["non_tradable_qoq"] = ntrad_qoq.get(date_str)
            item["non_tradable_yoy"] = ntrad_yoy.get(date_str)

            # QoQ or YoY が1つでもあるレコードのみ残す
            if item["all_qoq"] is not None or item["all_yoy"] is not None:
                result.append(item)

        return result

    def _compute_pct_change(
        self,
        index_map: Dict[str, float],
        all_dates: List[str],
        periods: int,
    ) -> Dict[str, float]:
        """Index値リストからpct_changeを算出"""
        if not index_map:
            return {}

        result = {}
        for i, date_str in enumerate(all_dates):
            if i < periods:
                continue
            current = index_map.get(date_str)
            prev = index_map.get(all_dates[i - periods])
            if current is not None and prev is not None and prev > 0:
                pct = ((current - prev) / prev) * 100
                result[date_str] = round(pct, 1)
        return result

    def _get_quarter_attempts(self, year: int, month: int) -> List[tuple]:
        """ダウンロード試行する四半期リスト（最新から過去3四半期分）"""
        quarter_months = [12, 9, 6, 3]
        attempts = []

        current_qm = None
        for qm in quarter_months:
            if month >= qm:
                current_qm = qm
                break

        if current_qm is None:
            current_qm = 12
            year -= 1

        y, qm = year, current_qm
        for _ in range(3):
            attempts.append((y, qm))
            idx = quarter_months.index(qm)
            if idx + 1 < len(quarter_months):
                qm = quarter_months[idx + 1]
            else:
                qm = quarter_months[0]
                y -= 1

        return attempts

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日を取得"""
        try:
            from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern(
                "Consumer Price Index",
                country="NZ",
            )
        except Exception as e:
            print(f"[NzCPI] Error getting next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[NzCPI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzCPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ Consumers Price Index (CPI)",
            "source": "Stats NZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_cpi_service = NzCpiService()
