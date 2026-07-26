"""
日本 現金給与額サービス
毎月勤労統計調査データを取得

指標:
- 現金給与総額 前年同月比 (%)

データソース:
- e-Stat: 毎月勤労統計調査
  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189720&fileKind=4

発表スケジュール:
- 1日〜10日: 速報値(p) 8:30 JST
- 17日〜月末: 確報値(r) 8:30 JST

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from io import BytesIO
import logging

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)
from services.japan.estat_monthly_release import (
    get_monthly_release_supplement,
    merge_supplement,
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cash_earnings_cache.json"


class CashEarningsService:
    """日本 現金給与額サービス"""

    DATA_CACHE_KEY = "japan:employment:cash_earnings:data"

    # FMP event mapping (same as scheduled wage)
    ECONALPHA_ID = "jp_average_cash_earnings_yoy"

    # e-Stat Excel download URL (現金給与総額)
    ESTAT_EXCEL_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189720&fileKind=4"

    def __init__(self):
        pass

    def get_cash_earnings_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        現金給与額データを取得

        Returns:
            {
                "data": [{"date": str, "value": float}, ...],
                "latest": {...},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data"),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # e-Stat Excelからデータを取得
        estat_data = self._load_from_estat()

        # 月次リリースファイルから最新月データを補完
        if estat_data:
            supplement = get_monthly_release_supplement(force_refresh=force_refresh)
            if supplement:
                sup_data = supplement.get("cash_earnings", [])
                if sup_data:
                    estat_data = merge_supplement(estat_data, sup_data)

        if estat_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            from services.usa.fmp_next_release_utils import guarded_last_updated
            latest = estat_data[-1] if estat_data else None
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "data": estat_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "e-Stat Excel",
            }

        # ファイルキャッシュからフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data"),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": None,
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_estat(self) -> Optional[List[Dict[str, Any]]]:
        """e-Stat Excelから現金給与額データを取得"""
        try:
            logger.info(f"Downloading cash earnings data from e-Stat: {self.ESTAT_EXCEL_URL}")

            response = requests.get(self.ESTAT_EXCEL_URL, timeout=60)
            if response.status_code != 200:
                logger.error(f"Failed to download from e-Stat: {response.status_code}")
                return None

            df = pd.read_excel(BytesIO(response.content), sheet_name=0, header=None)
            return self._process_excel(df)

        except Exception as e:
            logger.error(f"Error fetching cash earnings data from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_excel(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        現金給与額Excelデータを処理

        Excel構造:
        - Row 0-83: 指数データ（2020年=100）
        - Row 84-88: ヘッダー
        - Row 89: 前年比セクションヘッダー
        - Row 90+: 前年比データ
          - Column 0: 年
          - Column 1: 年平均
          - Column 8-19: 1月〜12月
        """
        try:
            logger.info(f"Processing cash earnings Excel with shape: {df.shape}")

            result = []

            # Find the YoY section (starts around row 89)
            yoy_start_row = None
            for i in range(80, min(100, len(df))):
                cell = str(df.iloc[i, 0]) if pd.notna(df.iloc[i, 0]) else ""
                if "前年比" in cell or "Year-on-year" in cell or "growth rate" in cell.lower():
                    yoy_start_row = i + 4  # Skip header rows (年, year, blank, then data)
                    break

            if yoy_start_row is None:
                # Try alternative detection - look for numeric year after row 90
                for i in range(90, min(110, len(df))):
                    cell = df.iloc[i, 0]
                    if pd.notna(cell):
                        try:
                            year = int(cell)
                            if 1950 <= year <= 2100:
                                yoy_start_row = i
                                break
                        except (ValueError, TypeError):
                            continue

            if yoy_start_row is None:
                logger.error("Could not find YoY section in Excel")
                return []

            logger.info(f"YoY section starts at row {yoy_start_row}")

            # Process YoY data
            for i in range(yoy_start_row, len(df)):
                row = df.iloc[i]
                year_val = row[0]

                if pd.isna(year_val):
                    continue

                try:
                    year = int(year_val)
                except (ValueError, TypeError):
                    continue

                if year < 1950 or year > 2100:
                    continue

                # Process each month (columns 8-19 for Jan-Dec)
                for month in range(1, 13):
                    col_idx = 7 + month  # Column 8 = Jan, 9 = Feb, ..., 19 = Dec
                    value = row[col_idx]

                    if pd.isna(value) or value == '-' or value == '':
                        continue

                    try:
                        val = float(value)
                        date_str = f"{year}-{month:02d}-01"

                        # Only include data from 2000 onwards
                        if year >= 2000:
                            result.append({
                                "date": date_str,
                                "value": round(val, 1)
                            })
                    except (ValueError, TypeError):
                        continue

            # Sort by date
            result.sort(key=lambda x: x["date"])

            logger.info(f"Processed {len(result)} cash earnings data points")
            if result:
                logger.info(f"Date range: {result[0]['date']} to {result[-1]['date']}")
                logger.info(f"Latest value: {result[-1]}")

            return result

        except Exception as e:
            logger.error(f"Error processing Excel: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(
            self.ECONALPHA_ID,
            last_updated_str,
            max_age_hours=72,
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        data_count = 0
        if cached_data:
            data_count = len(cached_data.get("data", []) or [])

        return {
            "indicator": "JP Cash Earnings (現金給与額)",
            "source": "e-Stat (厚生労働省)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": data_count,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
cash_earnings_service = CashEarningsService()
