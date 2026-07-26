"""
オーストラリア 住宅ローン金利水準サービス

データソース:
- RBA Statistical Tables F6 (Housing Lending Rates)
- https://www.rba.gov.au/statistics/tables/xls/f06hist.xlsx
- 月次、月末から5営業日後 11:30 AEDT/AEST 公表

取得系列（Seasonally Adjusted, All institutions）:
- FLRHOOVA: Outstanding Owner-occupied Variable-rate
- FLRHOOFA: Outstanding Owner-occupied Fixed-rate <= 3yr
- FLRHIOVA: Outstanding Investment Variable-rate
- FLRHIOFA: Outstanding Investment Fixed-rate <= 3yr
- FLRHOFVA: New loans Owner-occupied Variable-rate
- FLRHOFFA: New loans Owner-occupied Fixed-rate <= 3yr

発表スケジュール: 月次（月末から5営業日後 11:30 シドニー時間）
"""
import io
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.australia._rba_fetch import fetch_rba_xlsx

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_housing_lending_rates_cache.json"

# RBA F6 Excel URL
EXCEL_URL = "https://www.rba.gov.au/statistics/tables/xls/f06hist.xlsx"

# FMPイベントパターン（RBA金利決定と同じ発表サイクルで追う）
FMP_EVENT_PATTERN = "RBA Interest Rate Decision"
FMP_COUNTRY = "AU"

# 取得対象系列
# Outstanding（既存ローンの適用金利 → リセット後の実態を反映）
# New loans（新規貸出金利 → 更新時の水準を示す）
SERIES_CONFIG = {
    "outstanding_oo_variable": {
        "series_id": "FLRHOOVA",
        "label": "既存 自己居住 変動",
    },
    "outstanding_oo_fixed": {
        "series_id": "FLRHOOFA",
        "label": "既存 自己居住 固定(≤3yr)",
    },
    "outstanding_inv_variable": {
        "series_id": "FLRHIOVA",
        "label": "既存 投資 変動",
    },
    "outstanding_inv_fixed": {
        "series_id": "FLRHIOFA",
        "label": "既存 投資 固定(≤3yr)",
    },
    "new_oo_variable": {
        "series_id": "FLRHOFVA",
        "label": "新規 自己居住 変動",
    },
    "new_oo_fixed": {
        "series_id": "FLRHOFFA",
        "label": "新規 自己居住 固定(≤3yr)",
    },
}


class AuHousingLendingRatesService:
    """オーストラリア住宅ローン金利サービス"""

    DATA_CACHE_KEY = "australia:au_housing_lending_rates:data"

    def __init__(self):
        pass

    def _fetch_excel(self) -> Optional[bytes]:
        """RBA F6 Excelをダウンロード

        注意: ブラウザ UA 偽装は RBA WAF (Akamai) に 403 で弾かれる（2026-06確認）。
        共通ヘルパー fetch_rba_xlsx を使用すること。
        """
        logger.info(f"Downloading RBA F6 from {EXCEL_URL}")
        return fetch_rba_xlsx(EXCEL_URL, timeout=90)

    def _parse_excel(self, excel_bytes: bytes) -> Dict[str, List[Dict[str, Any]]]:
        """F6 Excelから複数系列を抽出"""
        try:
            import pandas as pd

            # pandasで読み込み（openpyxl直接だとdrawing参照エラーの可能性）
            df = pd.read_excel(
                io.BytesIO(excel_bytes),
                sheet_name="Data",
                header=None,
                engine="openpyxl",
            )

            # Row 10 (0-indexed) = Series ID行
            series_id_row = 10
            # Row 11+ = データ行

            # 各系列の列インデックスを特定
            col_map = {}
            for key, config in SERIES_CONFIG.items():
                sid = config["series_id"]
                for col_idx in range(1, df.shape[1]):
                    cell_val = df.iloc[series_id_row, col_idx]
                    if pd.notna(cell_val) and str(cell_val).strip() == sid:
                        col_map[key] = col_idx
                        logger.info(f"Found {sid} at column {col_idx}")
                        break

            if not col_map:
                logger.warning("No series found in F6 Excel")
                return {}

            # データを抽出
            result = {}
            for key, col_idx in col_map.items():
                observations = []
                for row_idx in range(11, df.shape[0]):
                    date_val = df.iloc[row_idx, 0]
                    if pd.isna(date_val):
                        continue

                    # 日付を変換
                    if isinstance(date_val, datetime):
                        date_str = date_val.strftime("%Y-%m-%d")
                    elif isinstance(date_val, str):
                        try:
                            dt = datetime.strptime(date_val.strip(), "%d-%b-%Y")
                            date_str = dt.strftime("%Y-%m-%d")
                        except ValueError:
                            continue
                    else:
                        continue

                    value = df.iloc[row_idx, col_idx]
                    if pd.notna(value):
                        observations.append({
                            "date": date_str,
                            "value": round(float(value), 2),
                        })

                result[key] = observations
                logger.info(f"Parsed {len(observations)} {SERIES_CONFIG[key]['label']} observations")

            return result

        except Exception as e:
            logger.error(f"Error parsing RBA F6 Excel: {e}")
            return {}

    def _build_data_points(self, parsed: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """複数系列を日付でマージ"""
        # 各系列を日付→値のマップに変換
        maps = {}
        all_dates = set()
        for key, observations in parsed.items():
            m = {obs["date"]: obs["value"] for obs in observations}
            maps[key] = m
            all_dates.update(m.keys())

        all_dates = sorted(all_dates)

        data_points = []
        for date_str in all_dates:
            point = {"date": date_str}
            has_any = False
            for key in SERIES_CONFIG.keys():
                val = maps.get(key, {}).get(date_str)
                point[key] = val
                if val is not None:
                    has_any = True

            if has_any:
                data_points.append(point)

        logger.info(f"Built {len(data_points)} merged data points")
        return data_points

    def get_au_housing_lending_rates_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """住宅ローン金利データを取得（キャッシュ付き）"""
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
                    }

        excel_bytes = self._fetch_excel()
        if excel_bytes:
            parsed = self._parse_excel(excel_bytes)
            if parsed:
                data_points = self._build_data_points(parsed)
                if data_points:
                    latest = data_points[-1]
                    next_release = self._get_next_release()
                    result = {
                        "data": data_points,
                        "latest": latest,
                        "metadata": {
                            "source": "Reserve Bank of Australia",
                            "indicator": "Housing Lending Rates (F6)",
                            "frequency": "monthly",
                            "unit": "% p.a.",
                        },
                        "next_release": next_release,
                    }
                    from services.usa.fmp_next_release_utils import guarded_last_updated
                    cache_payload = {**result, "last_updated": guarded_last_updated(self.DATA_CACHE_KEY, latest.get("date") if latest else None, datetime.now(JST).isoformat())}
                    redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                    self._save_file_cache(cache_payload)
                    return {**result, "cached": False, "source": "rba_excel"}

        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
            }

        return {
            "data": [], "latest": None,
            "metadata": {"source": "Reserve Bank of Australia", "error": "No data available"},
            "next_release": None, "cached": False, "source": "none",
        }

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        try:
            from services.australia.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            from services.australia.fmp_next_release_utils import should_refresh_by_pattern
            return should_refresh_by_pattern(
                FMP_EVENT_PATTERN, last_updated_str, country=FMP_COUNTRY
            )
        except Exception as e:
            logger.error(f"Error in should_refresh: {e}")
            return False

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "AU Housing Lending Rates",
            "source": "RBA F6",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
au_housing_lending_rates_service = AuHousingLendingRatesService()
