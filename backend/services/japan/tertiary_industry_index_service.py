"""
Japan Tertiary Industry Index Service
Fetches Tertiary Industry Activity Index (第三次産業活動指数) from METI Excel files

Data source: Ministry of Economy, Trade and Industry (METI)
MoM URL: https://www.meti.go.jp/statistics/tyo/sanzi/result/excel/b2020_ksmj.xlsx (季節調整済み前月比)
YoY URL: https://www.meti.go.jp/statistics/tyo/sanzi/result/excel/b2020_komj.xlsx (原数値前年比)

Returns:
- 前月比 (MoM) from seasonal adjusted data
- 前年比 (YoY) from original data

Release schedule: Monthly (around mid-month)
"""
import json
import logging
import io
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

try:
    from backend.core.redis_client import redis_client
    from backend.services.japan.fmp_next_release_utils import (
        get_next_release_from_fmp,
        should_refresh_by_fmp_schedule,
    )
except ImportError:
    from core.redis_client import redis_client
    from services.japan.fmp_next_release_utils import (
        get_next_release_from_fmp,
        should_refresh_by_fmp_schedule,
    )

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "tertiary_industry_index_cache.json"


class TertiaryIndustryIndexService:
    """Service for fetching Japan Tertiary Industry Activity Index from METI Excel files"""

    # METI Excel File URLs
    METI_MOM_URL = "https://www.meti.go.jp/statistics/tyo/sanzi/result/excel/b2020_ksmj.xlsx"
    METI_YOY_URL = "https://www.meti.go.jp/statistics/tyo/sanzi/result/excel/b2020_komj.xlsx"

    DATA_CACHE_KEY = "japan:tertiary_industry_index:data"
    ECONALPHA_ID = "jp_tertiary_industry_index"
    # FMPイベントパターン（DBマッピングがない場合のフォールバック）
    FMP_EVENT_PATTERNS = ["Tertiary Industry Index MoM"]

    def __init__(self):
        pass

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """Get next release date from FMP"""
        try:
            # まずDBマッピングを試し、なければデフォルトパターンを使用
            result = get_next_release_from_fmp(self.ECONALPHA_ID)
            if result is None:
                result = get_next_release_from_fmp(self.ECONALPHA_ID, patterns=self.FMP_EVENT_PATTERNS)
            return result
        except Exception as e:
            logger.warning(f"Error getting next release for {self.ECONALPHA_ID}: {e}")
            return None

    def _download_excel_file(self, url: str) -> Optional[bytes]:
        """
        Download the Excel file from METI with retry logic
        """
        max_retries = 3
        timeout = 300

        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to download Excel file from METI (attempt {attempt + 1}/{max_retries})")

                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,*/*',
                    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                })

                response = session.get(
                    url,
                    timeout=timeout,
                    stream=True,
                    allow_redirects=True
                )

                if response.status_code == 200:
                    content = b''
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            content += chunk

                    logger.info(f"Successfully downloaded Excel file ({len(content)} bytes)")
                    return content
                else:
                    logger.warning(f"Download attempt {attempt + 1} failed: HTTP {response.status_code}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(5)
                    continue

            except requests.exceptions.Timeout as e:
                logger.warning(f"Download attempt {attempt + 1} timed out: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(5)
                continue

            except Exception as e:
                logger.error(f"Error downloading Excel file (attempt {attempt + 1}): {e}", exc_info=True)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(5)
                    continue
                return None

        logger.error(f"Failed to download file after {max_retries} attempts")
        return None

    def _parse_mom_excel_data(self, excel_content: bytes) -> Optional[List[Dict]]:
        """
        Parse MoM data from Excel file (季節調整済み前月比)

        Structure similar to IIP:
        - Row 0-2: Headers
        - Row 3+: Data
        - Column 0: Item Code
        - Column 1: Item Name
        - Column 2: Weight
        - Column 3+: Monthly values

        Returns:
            List of data points with MoM values
        """
        try:
            excel_file = io.BytesIO(excel_content)
            xl = pd.ExcelFile(excel_file)
            logger.info(f"MoM Excel - Available sheets: {xl.sheet_names}")

            # Read ITA sheet (sheet index 1) - sheet 0 contains only usage notes
            df = pd.read_excel(excel_file, sheet_name=1, header=None)
            logger.info(f"MoM Excel sheet shape: {df.shape}")

            # Structure parameters
            HEADER_ROW = 2
            DATA_START_ROW = 3
            ITEM_CODE_COL = 0
            ITEM_NAME_COL = 1
            DATA_START_COL = 3

            # Get date headers from row 2
            header_row = df.iloc[HEADER_ROW]

            # Find the first data row (usually item code for 第三次産業活動指数)
            # Look for item code like "T0000000000" or the first numeric item
            target_row_idx = DATA_START_ROW  # Use first data row

            for row_idx in range(DATA_START_ROW, min(DATA_START_ROW + 20, len(df))):
                row = df.iloc[row_idx]
                item_name = str(row[ITEM_NAME_COL]).strip() if not pd.isna(row[ITEM_NAME_COL]) else ""
                # Target: 第三次産業総合 (K1D000000I) or similar total indicator
                if "第三次産業総合" in item_name or "第三次産業活動指数" in item_name:
                    target_row_idx = row_idx
                    break

            row = df.iloc[target_row_idx]
            item_code = str(row[ITEM_CODE_COL]).strip() if not pd.isna(row[ITEM_CODE_COL]) else "K1D000000I"
            item_name = str(row[ITEM_NAME_COL]).strip() if not pd.isna(row[ITEM_NAME_COL]) else "第三次産業総合"

            logger.info(f"Found target row at {target_row_idx}: {item_name} ({item_code})")

            # Extract monthly index values first
            index_values = []
            for col_idx in range(DATA_START_COL, len(row)):
                try:
                    date_header = header_row[col_idx]
                    if pd.isna(date_header):
                        continue

                    value = row[col_idx]
                    if pd.isna(value):
                        continue

                    try:
                        value_float = float(value)
                    except (ValueError, TypeError):
                        continue

                    # Parse date (format: 201801.0 = 2018年1月, or "p 202511" for preliminary)
                    try:
                        date_str = str(date_header).strip()

                        # Handle preliminary data prefix
                        if date_str.startswith('p '):
                            date_str = date_str[2:]

                        date_num = int(float(date_str))
                        year = date_num // 100
                        month = date_num % 100

                        if year > 1900 and 1 <= month <= 12:
                            date_formatted = f"{year}-{month:02d}-01"
                            index_values.append({
                                "date": date_formatted,
                                "index": value_float
                            })
                    except (ValueError, TypeError):
                        continue

                except Exception as e:
                    logger.debug(f"Error parsing column {col_idx}: {e}")
                    continue

            # Sort by date
            index_values.sort(key=lambda x: x['date'])

            # Calculate MoM change rate from index values
            # MoM = (current_index / previous_index - 1) * 100
            monthly_values = []
            for i in range(1, len(index_values)):
                prev_index = index_values[i - 1]['index']
                curr_index = index_values[i]['index']
                if prev_index and prev_index != 0:
                    mom_change = (curr_index / prev_index - 1) * 100
                    monthly_values.append({
                        "date": index_values[i]['date'],
                        "mom": round(mom_change, 2),
                        "index": round(curr_index, 1)  # Also include index value for reference
                    })

            logger.info(f"Calculated {len(monthly_values)} MoM change rates from index values")

            return monthly_values

        except Exception as e:
            logger.error(f"Error parsing MoM Excel data: {e}", exc_info=True)
            return None

    def _parse_yoy_excel_data(self, excel_content: bytes) -> Optional[List[Dict]]:
        """
        Parse YoY data from Excel file (原数値前年比)

        Returns:
            List of data points with YoY values
        """
        try:
            excel_file = io.BytesIO(excel_content)
            xl = pd.ExcelFile(excel_file)
            logger.info(f"YoY Excel - Available sheets: {xl.sheet_names}")

            # Read ITA sheet (sheet index 1) - sheet 0 contains only usage notes
            df = pd.read_excel(excel_file, sheet_name=1, header=None)
            logger.info(f"YoY Excel sheet shape: {df.shape}")

            HEADER_ROW = 2
            DATA_START_ROW = 3
            ITEM_CODE_COL = 0
            ITEM_NAME_COL = 1
            DATA_START_COL = 3

            header_row = df.iloc[HEADER_ROW]

            # Find target row
            target_row_idx = DATA_START_ROW
            for row_idx in range(DATA_START_ROW, min(DATA_START_ROW + 20, len(df))):
                row = df.iloc[row_idx]
                item_name = str(row[ITEM_NAME_COL]).strip() if not pd.isna(row[ITEM_NAME_COL]) else ""
                # Target: 第三次産業総合 (K1D000000I) or similar total indicator
                if "第三次産業総合" in item_name or "第三次産業活動指数" in item_name:
                    target_row_idx = row_idx
                    break

            row = df.iloc[target_row_idx]
            logger.info(f"YoY - Found target row at {target_row_idx}")

            # Extract monthly index values first
            index_values = []
            for col_idx in range(DATA_START_COL, len(row)):
                try:
                    date_header = header_row[col_idx]
                    if pd.isna(date_header):
                        continue

                    value = row[col_idx]
                    if pd.isna(value):
                        continue

                    try:
                        value_float = float(value)
                    except (ValueError, TypeError):
                        continue

                    try:
                        date_str = str(date_header).strip()
                        if date_str.startswith('p '):
                            date_str = date_str[2:]

                        date_num = int(float(date_str))
                        year = date_num // 100
                        month = date_num % 100

                        if year > 1900 and 1 <= month <= 12:
                            date_formatted = f"{year}-{month:02d}-01"
                            index_values.append({
                                "date": date_formatted,
                                "year": year,
                                "month": month,
                                "index": value_float
                            })
                    except (ValueError, TypeError):
                        continue

                except Exception as e:
                    logger.debug(f"Error parsing column {col_idx}: {e}")
                    continue

            # Sort by date
            index_values.sort(key=lambda x: x['date'])

            # Create lookup dict by (year, month)
            index_lookup = {(item['year'], item['month']): item['index'] for item in index_values}

            # Calculate YoY change rate from index values
            # YoY = (current_index / same_month_last_year_index - 1) * 100
            monthly_values = []
            for item in index_values:
                prev_year_key = (item['year'] - 1, item['month'])
                if prev_year_key in index_lookup:
                    prev_index = index_lookup[prev_year_key]
                    if prev_index and prev_index != 0:
                        yoy_change = (item['index'] / prev_index - 1) * 100
                        monthly_values.append({
                            "date": item['date'],
                            "yoy": round(yoy_change, 2)
                        })

            monthly_values.sort(key=lambda x: x['date'])
            logger.info(f"Calculated {len(monthly_values)} YoY change rates from index values")

            return monthly_values

        except Exception as e:
            logger.error(f"Error parsing YoY Excel data: {e}", exc_info=True)
            return None

    def _fetch_data(self) -> Optional[Dict[str, Any]]:
        """
        Fetch Tertiary Industry Index data from METI Excel files
        """
        try:
            logger.info("Fetching Japan Tertiary Industry Index data from METI Excel")

            # Download MoM Excel
            mom_content = self._download_excel_file(self.METI_MOM_URL)
            mom_data = []
            if mom_content:
                mom_data = self._parse_mom_excel_data(mom_content) or []

            # Download YoY Excel
            yoy_content = self._download_excel_file(self.METI_YOY_URL)
            yoy_data = []
            if yoy_content:
                yoy_data = self._parse_yoy_excel_data(yoy_content) or []

            # Merge MoM and YoY data
            merged_data = {}

            for item in mom_data:
                date = item['date']
                if date not in merged_data:
                    merged_data[date] = {"date": date}
                merged_data[date]['mom'] = round(item['mom'], 2) if item.get('mom') is not None else None

            for item in yoy_data:
                date = item['date']
                if date not in merged_data:
                    merged_data[date] = {"date": date}
                merged_data[date]['yoy'] = round(item['yoy'], 2) if item.get('yoy') is not None else None

            # Sort by date (descending - most recent first)
            processed_data = sorted(merged_data.values(), key=lambda x: x['date'], reverse=True)

            if not processed_data:
                logger.error("No data extracted from Excel files")
                return None

            logger.info(f"Merged {len(processed_data)} data points")

            return {
                "data": processed_data,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Ministry of Economy, Trade and Industry (METI)"
            }

        except Exception as e:
            logger.error(f"Error fetching Tertiary Industry Index data: {e}", exc_info=True)
            return None

    def get_tertiary_industry_index_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get Japan Tertiary Industry Index data with caching"""
        # Check Redis cache
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    logger.info("Returning cached Tertiary Industry Index data from Redis")
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("data", [{}])[0] if cached_data.get("data") else None,
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

            # File cache check
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    logger.info("Returning cached Tertiary Industry Index data from file")
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("data", [{}])[0] if file_cache.get("data") else None,
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # Fetch fresh data
        result = self._fetch_data()
        if result:
            cache_payload = {
                "data": result["data"],
                "last_updated": result["last_updated"],
                "source": result["source"]
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result["data"],
                "latest": result["data"][0] if result["data"] else None,
                "next_release": self._get_next_release(),
                "cached": False,
                "source": "meti",
                "last_updated": result["last_updated"]
            }

        # File cache fallback
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("data", [{}])[0] if file_cache.get("data") else None,
                "next_release": self._get_next_release(),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """Check if cache should be refreshed based on FMP schedule"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

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
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Japan Tertiary Industry Activity Index",
            "source": "METI",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("data", [{}])[0] if cached_data and cached_data.get("data") else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# Singleton instance
tertiary_industry_index_service = TertiaryIndustryIndexService()
