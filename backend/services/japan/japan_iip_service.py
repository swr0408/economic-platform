"""
Japan Industrial Production Index (IIP) Service
Fetches IIP data (鉱工業生産指数) from METI Excel files

Data source: Ministry of Economy, Trade and Industry (METI)
URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_gsm1j.xlsx (季節調整済み)

Returns:
- 前月比 (MoM) calculated from seasonal adjusted index

Release schedule: Monthly around mid-month
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
    from backend.services.japan.fmp_next_release_utils import get_next_release_from_fmp
except ImportError:
    from core.redis_client import redis_client
    from services.japan.fmp_next_release_utils import get_next_release_from_fmp

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_iip_cache.json"


class JapanIIPService:
    """Service for fetching Japan Industrial Production Index data from METI Excel files"""

    # METI Excel File Download URL (季節調整済み指数)
    METI_IIP_URL = "https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_gsm1j.xlsx"

    DATA_CACHE_KEY = "japan:iip:data"

    # FMP event pattern for next release
    INDICATOR_ID = "jp_industrial_production"

    def __init__(self):
        pass

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """Get next release date from FMP"""
        try:
            return get_next_release_from_fmp(self.INDICATOR_ID)
        except Exception as e:
            logger.warning(f"Error getting next release for {self.INDICATOR_ID}: {e}")
            return None

    def _download_excel_file(self) -> Optional[bytes]:
        """
        Download the Excel file from METI with retry logic.
        Fast-fail: 1 attempt, 20s timeout — caller must handle failure with cache fallback.
        """
        max_retries = 1
        timeout = 20

        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to download IIP Excel file from METI (attempt {attempt + 1}/{max_retries})")

                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,*/*',
                    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                })

                response = session.get(
                    self.METI_IIP_URL,
                    timeout=timeout,
                    stream=True,
                    allow_redirects=True
                )

                if response.status_code == 200:
                    content = b''
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            content += chunk

                    logger.info(f"Successfully downloaded IIP Excel file ({len(content)} bytes)")
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
                logger.error(f"Error downloading IIP Excel file (attempt {attempt + 1}): {e}", exc_info=True)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(5)
                    continue
                return None

        logger.error(f"Failed to download IIP file after {max_retries} attempts")
        return None

    def _parse_excel_data(self, excel_content: bytes) -> Optional[List[Dict]]:
        """
        Parse IIP data from Excel file (生産 sheet - second sheet by index)

        Column structure:
        - Column 0: 品目番号 (Item Code) - e.g., 1000000000
        - Column 1: 品目名称 (Item Name) - e.g., 鉱工業
        - Column 2: ウェイト (Weight)
        - Column 3+: Monthly index values

        Args:
            excel_content: Excel file content as bytes

        Returns:
            List of data points with item codes, names, and production index values
        """
        try:
            excel_file = io.BytesIO(excel_content)
            xl = pd.ExcelFile(excel_file)
            logger.info(f"Available sheets: {len(xl.sheet_names)} sheets")

            # Read the second sheet (index 1) which is the production sheet
            df = pd.read_excel(excel_file, sheet_name=xl.sheet_names[1], header=None)
            logger.info(f"Production sheet shape: {df.shape}")

            # Fixed structure
            HEADER_ROW = 2
            DATA_START_ROW = 3
            ITEM_CODE_COL = 0
            ITEM_NAME_COL = 1
            DATA_START_COL = 3

            # Get date headers from row 2
            header_row = df.iloc[HEADER_ROW]

            # Find the row with item code 1000000000 (鉱工業)
            target_row_idx = None
            for row_idx in range(DATA_START_ROW, len(df)):
                row = df.iloc[row_idx]
                if not pd.isna(row[ITEM_CODE_COL]):
                    try:
                        item_code = str(int(float(row[ITEM_CODE_COL])))
                        if item_code == '1000000000':
                            target_row_idx = row_idx
                            break
                    except (ValueError, TypeError):
                        continue

            if target_row_idx is None:
                logger.error("Could not find item code 1000000000")
                return None

            row = df.iloc[target_row_idx]
            item_code = '1000000000'
            item_name = str(row[ITEM_NAME_COL]).strip() if not pd.isna(row[ITEM_NAME_COL]) else "鉱工業"

            logger.info(f"Found item 1000000000 at row {target_row_idx}: {item_name}")

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

            # Sort by date (oldest first) for MoM calculation
            monthly_values.sort(key=lambda x: x['date'])

            logger.info(f"Extracted {len(monthly_values)} monthly values")

            # Calculate MoM (Month-over-Month) change
            flattened_data = []
            for i in range(len(monthly_values)):
                current = monthly_values[i]

                mom_change = None
                if i > 0:
                    previous = monthly_values[i - 1]
                    if previous['value'] != 0:
                        mom_change = ((current['value'] - previous['value']) / previous['value']) * 100

                flattened_data.append({
                    "date": current['date'],
                    "item_code": item_code,
                    "item_name": item_name,
                    "category": "鉱工業",
                    "value": current['value'],
                    "mom_change": mom_change
                })

            # Sort by date (most recent first)
            flattened_data = sorted(flattened_data, key=lambda x: x['date'], reverse=True)

            logger.info(f"Created {len(flattened_data)} data points with MoM")
            if flattened_data:
                logger.info(f"Sample data (first 3 points): {flattened_data[:3]}")

            return flattened_data

        except Exception as e:
            logger.error(f"Error parsing Excel data: {e}", exc_info=True)
            return None

    def _fetch_iip_data(self) -> Optional[Dict[str, Any]]:
        """
        Fetch IIP data from METI Excel file
        """
        try:
            logger.info("Fetching Japan IIP data from METI Excel")

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
                    "item_code": item['item_code'],
                    "item_name": item['item_name'],
                    "category": item['category'],
                    "value": round(item['value'], 1) if item['value'] is not None else None,
                    "mom_change": round(item['mom_change'], 2) if item['mom_change'] is not None else None
                })

            return {
                "data": processed_data,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Ministry of Economy, Trade and Industry (METI)"
            }

        except Exception as e:
            logger.error(f"Error fetching IIP data: {e}", exc_info=True)
            return None

    def get_iip_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get Japan IIP data with caching.

        Strategy:
        1. Fresh cache hit → return immediately.
        2. Circuit breaker: if METI failed in the last 5 minutes, skip fetch and serve stale cache.
        3. Otherwise try METI; on success update both caches and clear breaker.
        4. On failure set breaker (5 min cooldown) and fall back to Redis → file cache → empty.
        """
        cached_data = redis_client.get(self.DATA_CACHE_KEY)
        negative_key = self.DATA_CACHE_KEY + ":fetch_failed"

        # 1) Fresh cache hit
        if not force_refresh and cached_data:
            last_updated_str = cached_data.get("last_updated")
            if last_updated_str and not self._should_refresh(last_updated_str):
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("data", [{}])[0] if cached_data.get("data") else None,
                    "next_release": self._get_next_release(),
                    "cached": True,
                    "source": "redis",
                    "last_updated": last_updated_str
                }

        # 2) Circuit breaker: recent METI failure → skip fetch, serve any cache
        if not force_refresh and redis_client.exists(negative_key):
            if cached_data:
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("data", [{}])[0] if cached_data.get("data") else None,
                    "next_release": self._get_next_release(),
                    "cached": True,
                    "source": "redis (stale, breaker)",
                    "last_updated": cached_data.get("last_updated")
                }
            file_cache = self._load_file_cache()
            if file_cache:
                return {
                    "data": file_cache.get("data", []),
                    "latest": file_cache.get("data", [{}])[0] if file_cache.get("data") else None,
                    "next_release": self._get_next_release(),
                    "cached": True,
                    "source": "file (stale, breaker)",
                    "last_updated": file_cache.get("last_updated")
                }

        # 3) Try fresh fetch
        result = self._fetch_iip_data()
        if result:
            cache_payload = {
                "data": result["data"],
                "last_updated": result["last_updated"],
                "source": result["source"]
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)
            redis_client.delete(negative_key)

            return {
                "data": result["data"],
                "latest": result["data"][0] if result["data"] else None,
                "next_release": self._get_next_release(),
                "cached": False,
                "source": "meti",
                "last_updated": result["last_updated"]
            }

        # 4) Fetch failed → set breaker and serve any cache
        redis_client.set(negative_key, {"failed_at": datetime.now(JST).isoformat()}, expire=300)

        if cached_data:
            return {
                "data": cached_data.get("data", []),
                "latest": cached_data.get("data", [{}])[0] if cached_data.get("data") else None,
                "next_release": self._get_next_release(),
                "cached": True,
                "source": "redis (stale, fallback)",
                "last_updated": cached_data.get("last_updated")
            }
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
        """Check if cache should be refreshed.

        IIP is monthly data — 7-day freshness window aligns with release cadence and
        absorbs occasional METI downtime without forcing every request to hit METI.
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            cache_age_hours = (now - last_updated).total_seconds() / 3600

            if cache_age_hours > 24 * 7:
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
            "indicator": "Japan Industrial Production Index (IIP)",
            "source": "METI",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("data", [{}])[0] if cached_data and cached_data.get("data") else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# Singleton instance
japan_iip_service = JapanIIPService()
