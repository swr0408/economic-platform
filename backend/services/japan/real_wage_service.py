"""
日本 実質賃金サービス
毎月勤労統計調査データを取得

指標:
- 実質賃金指数 前年同月比 (%) - 全事業所版
- 実質賃金指数 前年同月比 (%) - 共通事業所版

データソース:
- e-Stat: 毎月勤労統計調査
  - 全事業所版: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189738&fileKind=4
  - 共通事業所版: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040277106&fileKind=4

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

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "real_wage_cache.json"


class RealWageService:
    """日本 実質賃金サービス"""

    DATA_CACHE_KEY = "japan:employment:real_wage:data"

    # FMP event mapping (same as scheduled wage)
    ECONALPHA_ID = "jp_average_cash_earnings_yoy"

    # e-Stat Excel download URLs
    ESTAT_ALL_EXCEL_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032189738&fileKind=4"  # 全事業所版
    ESTAT_COMMON_EXCEL_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040277106&fileKind=4"  # 共通事業所版

    def __init__(self):
        pass

    def get_real_wage_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        実質賃金データを取得（2系列）

        Returns:
            {
                "all": {"data": [...], "latest": {...}},  # 全事業所版
                "common": {"data": [...], "latest": {...}},  # 共通事業所版
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
                        "all": cached_data.get("all"),
                        "common": cached_data.get("common"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # e-Stat Excelからデータを取得（2系列）
        all_data = self._load_from_estat(self.ESTAT_ALL_EXCEL_URL, "全事業所版", 80)
        common_data = self._load_from_estat(self.ESTAT_COMMON_EXCEL_URL, "共通事業所版", 40)

        if all_data or common_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "all": {
                    "data": all_data,
                    "latest": all_data[-1] if all_data else None,
                } if all_data else None,
                "common": {
                    "data": common_data,
                    "latest": common_data[-1] if common_data else None,
                } if common_data else None,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
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
                "all": file_cache.get("all"),
                "common": file_cache.get("common"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "all": None,
            "common": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_estat(self, url: str, name: str, search_start_row: int) -> Optional[List[Dict[str, Any]]]:
        """e-Stat Excelから実質賃金データを取得"""
        try:
            logger.info(f"Downloading real wage data ({name}) from e-Stat: {url}")

            response = requests.get(url, timeout=60)
            if response.status_code != 200:
                logger.error(f"Failed to download from e-Stat: {response.status_code}")
                return None

            df = pd.read_excel(BytesIO(response.content), sheet_name=0, header=None)
            return self._process_excel(df, name, search_start_row)

        except Exception as e:
            logger.error(f"Error fetching real wage data ({name}) from e-Stat: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_excel(self, df: pd.DataFrame, name: str, search_start_row: int) -> List[Dict[str, Any]]:
        """
        実質賃金Excelデータを処理

        Excel構造:
        - 前年比セクション以降のデータを抽出
          - Column 0: 年
          - Column 1: 年平均
          - Column 8-19: 1月〜12月
        """
        try:
            logger.info(f"Processing real wage Excel ({name}) with shape: {df.shape}")

            result = []

            # Find the YoY section
            yoy_start_row = None
            for i in range(search_start_row, min(search_start_row + 30, len(df))):
                cell = str(df.iloc[i, 0]) if pd.notna(df.iloc[i, 0]) else ""
                if "前年比" in cell or "Year-on-year" in cell or "growth rate" in cell.lower():
                    yoy_start_row = i + 3  # Skip header rows
                    break

            if yoy_start_row is None:
                # Try alternative detection - look for numeric year
                for i in range(search_start_row + 10, min(search_start_row + 40, len(df))):
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
                logger.error(f"Could not find YoY section in Excel ({name})")
                return []

            logger.info(f"YoY section starts at row {yoy_start_row} ({name})")

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

            logger.info(f"Processed {len(result)} real wage data points ({name})")
            if result:
                logger.info(f"Date range: {result[0]['date']} to {result[-1]['date']}")
                logger.info(f"Latest value: {result[-1]}")

            return result

        except Exception as e:
            logger.error(f"Error processing Excel ({name}): {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(
            self.ECONALPHA_ID,
            last_updated_str
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

        all_count = 0
        common_count = 0
        if cached_data:
            all_data = cached_data.get("all")
            common_data = cached_data.get("common")
            all_count = len(all_data.get("data", [])) if all_data else 0
            common_count = len(common_data.get("data", [])) if common_data else 0

        return {
            "indicator": "JP Real Wage (実質賃金)",
            "source": "e-Stat (厚生労働省)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "all": all_count,
                "common": common_count,
            },
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
real_wage_service = RealWageService()
