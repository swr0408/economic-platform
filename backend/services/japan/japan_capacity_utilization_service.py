"""
Japan Capacity Utilization Service
Fetches Capacity Utilization data (稼働率指数) from METI Excel files

Data source: Ministry of Economy, Trade and Industry (METI)
URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ngsm1j.xlsx
Release schedule: Same as IIP (Industrial Production Index)
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
except ImportError:
    from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_capacity_utilization_cache.json"


class JapanCapacityUtilizationService:
    """Service for fetching Japan Capacity Utilization data from METI Excel files"""

    # METI Excel File Download URL
    METI_CAPACITY_URL = "https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ngsm1j.xlsx"

    DATA_CACHE_KEY = "japan:capacity_utilization:data"

    def __init__(self):
        pass

    def _download_excel_file(self) -> Optional[bytes]:
        """
        Download the Excel file from METI with retry logic
        """
        max_retries = 3
        timeout = 300  # 5 minutes timeout

        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to download Capacity Utilization Excel file from METI (attempt {attempt + 1}/{max_retries})")

                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,*/*',
                    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                })

                response = session.get(
                    self.METI_CAPACITY_URL,
                    timeout=timeout,
                    stream=True,
                    allow_redirects=True
                )

                if response.status_code == 200:
                    content = b''
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            content += chunk

                    logger.info(f"Successfully downloaded Capacity Utilization Excel file ({len(content)} bytes)")
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
                logger.error(f"Error downloading Capacity Utilization Excel file (attempt {attempt + 1}): {e}", exc_info=True)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(5)
                    continue
                return None

        logger.error(f"Failed to download Capacity Utilization file after {max_retries} attempts")
        return None

    def _parse_excel_data(self, excel_content: bytes) -> Optional[List[Dict]]:
        """
        Parse Capacity Utilization data from Excel file (稼働率 sheet)

        Structure:
        - Row 3 (index 3): Data row with item "製造工業" (Manufacturing Industry)
        - Column 0: Item code
        - Column 1: Item name (品目名称) - "製造工業"
        - Column 2: Weight (ウェイト)
        - Column 3+: Monthly index values
        """
        try:
            excel_file = io.BytesIO(excel_content)
            xl = pd.ExcelFile(excel_file)
            logger.info(f"Available sheets: {xl.sheet_names}")

            # Find the sheet with "稼働率" in the name
            capacity_sheet = None
            for sheet_name in xl.sheet_names:
                if '稼働率' in str(sheet_name):
                    capacity_sheet = sheet_name
                    break

            if not capacity_sheet:
                logger.error("Could not find 稼働率 sheet")
                return None

            logger.info(f"Using sheet: {capacity_sheet}")

            # Read the capacity utilization sheet
            df = pd.read_excel(excel_file, sheet_name=capacity_sheet, header=None)
            logger.info(f"Capacity sheet shape: {df.shape}")

            # Fixed structure
            HEADER_ROW = 2
            DATA_ROW = 3  # Row 4 in Excel (0-indexed row 3) contains "製造工業"
            ITEM_NAME_COL = 1
            DATA_START_COL = 3

            # Get date headers from row 2
            header_row = df.iloc[HEADER_ROW]

            # Get the manufacturing industry row
            row = df.iloc[DATA_ROW]
            item_name = str(row[ITEM_NAME_COL]).strip() if not pd.isna(row[ITEM_NAME_COL]) else "製造工業"

            logger.info(f"Found item at row {DATA_ROW}: {item_name}")

            # Extract all monthly values with dates
            monthly_values = []
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

                        # Handle preliminary data prefix (e.g., "p 202511")
                        if date_str.startswith('p '):
                            date_str = date_str[2:]  # Remove "p " prefix

                        date_num = int(float(date_str))
                        year = date_num // 100
                        month = date_num % 100

                        if year > 1900 and 1 <= month <= 12:
                            date_formatted = f"{year}-{month:02d}-01"
                            monthly_values.append({
                                "date": date_formatted,
                                "value": value_float
                            })
                    except (ValueError, TypeError):
                        continue

                except (ValueError, AttributeError, TypeError, IndexError) as e:
                    logger.debug(f"Error parsing column {col_idx}: {e}")
                    continue

            # Sort by date (oldest first)
            monthly_values.sort(key=lambda x: x['date'])

            logger.info(f"Extracted {len(monthly_values)} monthly values")

            # Create data list
            flattened_data = []
            for current in monthly_values:
                flattened_data.append({
                    "date": current['date'],
                    "item_name": item_name,
                    "category": "製造工業",
                    "value": current['value'],
                })

            # Sort by date (most recent first)
            flattened_data = sorted(flattened_data, key=lambda x: x['date'], reverse=True)

            logger.info(f"Created {len(flattened_data)} data points")
            if flattened_data:
                logger.info(f"Sample data (first 3 points): {flattened_data[:3]}")

            return flattened_data

        except Exception as e:
            logger.error(f"Error parsing Excel data: {e}", exc_info=True)
            return None

    def _fetch_capacity_data(self) -> Optional[Dict[str, Any]]:
        """
        Fetch Capacity Utilization data from METI Excel file
        """
        try:
            logger.info("Fetching Japan Capacity Utilization data from METI Excel")

            excel_content = self._download_excel_file()
            if not excel_content:
                logger.error("Failed to download Excel file")
                return None

            data_points = self._parse_excel_data(excel_content)
            if not data_points:
                logger.error("Failed to parse Excel data")
                return None

            processed_data = []
            for item in data_points:
                processed_data.append({
                    "date": item['date'],
                    "item_name": item['item_name'],
                    "category": item['category'],
                    "value": round(item['value'], 1) if item['value'] is not None else None,
                })

            return {
                "data": processed_data,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Ministry of Economy, Trade and Industry (METI)"
            }

        except Exception as e:
            logger.error(f"Error fetching Capacity Utilization data: {e}", exc_info=True)
            return None

    def get_capacity_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get Japan Capacity Utilization data with caching"""
        # Check Redis cache
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("data", [{}])[0] if cached_data.get("data") else None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # Fetch fresh data
        result = self._fetch_capacity_data()
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
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """Check if cache should be refreshed (24 hours)"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            cache_age_hours = (now - last_updated).total_seconds() / 3600

            if cache_age_hours > 24:
                return True

            return False
        except Exception:
            return True

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
            "indicator": "Japan Capacity Utilization Index",
            "source": "METI",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("data", [{}])[0] if cached_data and cached_data.get("data") else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# Singleton instance
japan_capacity_utilization_service = JapanCapacityUtilizationService()
