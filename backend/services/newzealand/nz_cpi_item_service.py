"""
NZ CPI項目別サービス

指標:
- Food（食料）: CPIQ.SE901
- Actual rentals for housing（家賃）: CPIQ.SE9041
- Purchase of housing（住宅購入）: CPIQ.SE9TN04201
- Electricity（電気）: CPIQ.SE9TN04501
- Gas（ガス）: CPIQ.SE9TN04502

データソース:
- Stats NZ Consumers Price Index
- https://www.stats.govt.nz/indicators/consumers-price-index-cpi/

取得方法:
- index-numbers.csv から Food, Rentals を取得
- tradeables-and-non-tradeables.csv から Purchase of housing, Electricity, Gas を取得
- Index値から YoY% を算出

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
DATA_CACHE_FILE = CACHE_DIR / "nz_cpi_item_cache.json"

# Stats NZ CPI CSV URL パターン
QUARTER_MONTHS = {
    3: ("March", "march"),
    6: ("June", "june"),
    9: ("September", "september"),
    12: ("December", "december"),
}

# 対象系列（index-numbers.csv に存在）
INDEX_SERIES = {
    "food": "CPIQ.SE901",
    "rentals": "CPIQ.SE9041",
}

# 対象系列（tradeables-and-non-tradeables.csv に存在）
TRADEABLE_SERIES = {
    "purchase_housing": "CPIQ.SE9TN04201",
    "electricity": "CPIQ.SE9TN04501",
    "gas": "CPIQ.SE9TN04502",
}


def _build_csv_url(year: int, quarter_month: int, csv_type: str) -> str:
    """Stats NZ CPI CSV URLを生成"""
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


class NzCpiItemService:
    """NZ CPI項目別サービス"""

    DATA_CACHE_KEY = "newzealand:nz_cpi_item:data"

    def __init__(self):
        pass

    def get_nz_cpi_item_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ CPI項目別データを取得"""

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
                    "indicator": "CPI Item Breakdown",
                    "description": "NZ CPI項目別（前年比）",
                    "unit": "% YoY",
                    "frequency": "quarterly",
                    "series": {
                        "food": INDEX_SERIES["food"],
                        "rentals": INDEX_SERIES["rentals"],
                        "purchase_housing": TRADEABLE_SERIES["purchase_housing"],
                        "electricity": TRADEABLE_SERIES["electricity"],
                        "gas": TRADEABLE_SERIES["gas"],
                    },
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
        """Stats NZ CPI CSVから項目別データを取得"""
        try:
            now = datetime.now(JST)
            attempts = self._get_quarter_attempts(now.year, now.month)

            # 1. index-numbers.csv をダウンロード
            df_idx = None
            for year, qm in attempts:
                url = _build_csv_url(year, qm, "index-numbers")
                print(f"[NzCpiItem] Trying index-numbers: {url}")
                try:
                    resp = requests.get(url, timeout=120)
                    if resp.status_code == 200 and len(resp.content) > 5000:
                        df_idx = pd.read_csv(io.StringIO(resp.text), low_memory=False)
                        month_cap, _ = QUARTER_MONTHS[qm]
                        print(f"[NzCpiItem] Downloaded index-numbers {month_cap} {year} ({len(df_idx)} rows)")
                        break
                except Exception as e:
                    print(f"[NzCpiItem] Error: {e}")
                    continue

            if df_idx is None:
                print("[NzCpiItem] Failed to download index-numbers CSV")
                return None

            # 2. tradeables-and-non-tradeables.csv をダウンロード
            df_tn = None
            for year, qm in attempts:
                url = _build_csv_url(year, qm, "tradeables-and-non-tradeables")
                print(f"[NzCpiItem] Trying tradeables: {url}")
                try:
                    resp = requests.get(url, timeout=120)
                    if resp.status_code == 200 and len(resp.content) > 5000:
                        df_tn = pd.read_csv(io.StringIO(resp.text), low_memory=False)
                        month_cap, _ = QUARTER_MONTHS[qm]
                        print(f"[NzCpiItem] Downloaded tradeables {month_cap} {year} ({len(df_tn)} rows)")
                        break
                except Exception as e:
                    print(f"[NzCpiItem] Error: {e}")
                    continue

            # 各系列のIndex値を抽出
            index_maps: Dict[str, Dict[str, float]] = {}

            for key, series_ref in INDEX_SERIES.items():
                index_maps[key] = self._extract_index(df_idx, series_ref, key)

            if df_tn is not None:
                for key, series_ref in TRADEABLE_SERIES.items():
                    index_maps[key] = self._extract_index(df_tn, series_ref, key)

            # 全日付を集約（全系列で共通する日付範囲）
            all_dates = set()
            for mapping in index_maps.values():
                all_dates.update(mapping.keys())
            all_dates_sorted = sorted(all_dates)

            # YoY% を算出してマージ
            yoy_maps: Dict[str, Dict[str, float]] = {}
            for key, mapping in index_maps.items():
                yoy_maps[key] = self._compute_yoy(mapping, all_dates_sorted)

            result = []
            for date_str in all_dates_sorted:
                if date_str < "2000-01-01":
                    continue
                item: Dict[str, Any] = {"date": date_str}
                has_any = False
                for key in ["food", "rentals", "purchase_housing", "electricity", "gas"]:
                    val = yoy_maps.get(key, {}).get(date_str)
                    item[f"{key}_yoy"] = val
                    if val is not None:
                        has_any = True
                if has_any:
                    result.append(item)

            if result:
                print(f"[NzCpiItem] Total {len(result)} records")
                print(f"[NzCpiItem] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[NzCpiItem] Latest: Food={latest.get('food_yoy')}%, Rentals={latest.get('rentals_yoy')}%")
                print(f"[NzCpiItem] Housing={latest.get('purchase_housing_yoy')}%, Elec={latest.get('electricity_yoy')}%, Gas={latest.get('gas_yoy')}%")

            return result

        except Exception as e:
            print(f"[NzCpiItem] Error loading from Stats NZ: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_index(self, df: pd.DataFrame, series_ref: str, label: str) -> Dict[str, float]:
        """DataFrameから指定系列のIndex値を抽出"""
        subset = df[df["Series_reference"] == series_ref].copy()
        if len(subset) == 0:
            print(f"[NzCpiItem] {label} ({series_ref}): NOT FOUND")
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

        print(f"[NzCpiItem] {label} ({series_ref}): {len(mapping)} records")
        return mapping

    def _compute_yoy(self, index_map: Dict[str, float], all_dates: List[str]) -> Dict[str, float]:
        """Index値からYoY%を算出"""
        if not index_map:
            return {}

        result = {}
        for i, date_str in enumerate(all_dates):
            if i < 4:
                continue
            current = index_map.get(date_str)
            prev = index_map.get(all_dates[i - 4])
            if current is not None and prev is not None and prev > 0:
                pct = ((current - prev) / prev) * 100
                result[date_str] = round(pct, 1)
        return result

    def _get_quarter_attempts(self, year: int, month: int) -> List[tuple]:
        """ダウンロード試行する四半期リスト"""
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
            print(f"[NzCpiItem] Error getting next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[NzCpiItem] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzCpiItem] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ CPI Item Breakdown",
            "source": "Stats NZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_cpi_item_service = NzCpiItemService()
