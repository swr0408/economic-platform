"""
Japan Economy Watcher Survey Service
Fetches Economy Watcher (景気ウォッチャー調査) data from Cabinet Office

This service fetches data from a fixed URL that is updated monthly.

Data items:
- total: Total DI (合計)
- household: Household-related DI (家計動向関連)
- corporate: Corporate-related DI (企業動向関連)
- employment: Employment-related DI (雇用関連)

Source: Cabinet Office (内閣府)
Release: Monthly, around 8th-14th
"""
import json
import logging
import requests
import pandas as pd
import io
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    from backend.core.redis_client import redis_client
except ImportError:
    from core.redis_client import redis_client

logger = logging.getLogger(__name__)


class EconomyWatcherService:
    """Service for fetching Japan Economy Watcher Survey data"""

    # Cache settings
    CACHE_KEY_CURRENT = "japan:economy_watcher:current"
    CACHE_KEY_OUTLOOK = "japan:economy_watcher:outlook"
    CACHE_TTL = 60 * 60 * 24 * 7  # 7 days

    # Cabinet Office Economy Watcher Survey URL
    ECONOMY_WATCHER_URL = "https://www5.cao.go.jp/keizai3/watcher/watcher5.xls"

    def __init__(self):
        """Initialize Economy Watcher service"""
        self.cache_dir = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy_watcher"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _download_excel_file(self) -> Optional[bytes]:
        """
        Download the Excel file from Cabinet Office

        Returns:
            Excel file content as bytes
        """
        try:
            logger.info(f"Downloading Economy Watcher Survey data from {self.ECONOMY_WATCHER_URL}")
            response = requests.get(self.ECONOMY_WATCHER_URL, timeout=30)

            if response.status_code == 200:
                logger.info(f"Successfully downloaded Economy Watcher file ({len(response.content)} bytes)")
                return response.content
            else:
                logger.error(f"Failed to download: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error downloading Economy Watcher file: {e}")
            return None

    def _parse_sheet_data(self, excel_content: bytes, sheet_index: int, data_type: str) -> Optional[List[Dict]]:
        """
        Parse Economy Watcher data from a specific sheet

        Sheet structure:
        - Sheet 0: Current conditions (現状判断)
        - Sheet 1: Outlook (先行き判断)
        - Row 6+: Data starts from row 6 (index 6)
        - Column 1: Year (e.g., "2002年")
        - Column 2: Month (e.g., 1.0)
        - Column 3: Total (合計)
        - Column 4: Household-related (家計動向関連)
        - Column 9: Corporate-related (企業動向関連)
        - Column 12: Employment-related (雇用関連)

        Args:
            excel_content: Excel file content as bytes
            sheet_index: Sheet index (0 for current, 1 for outlook)
            data_type: 'current' or 'outlook'

        Returns:
            List of data points
        """
        try:
            # Read Excel file
            excel_file = io.BytesIO(excel_content)
            df = pd.read_excel(excel_file, sheet_name=sheet_index, header=None)

            logger.info(f"Excel sheet {sheet_index} ({data_type}) shape: {df.shape}")

            # Parse data points (starts from row 6)
            data_points = []
            current_year = None

            for row_idx in range(6, len(df)):
                try:
                    row = df.iloc[row_idx]

                    # Get year from column 1 (format: "2002年" or NaN for continuation)
                    year_val = row[1]
                    if pd.notna(year_val) and isinstance(year_val, str) and '年' in str(year_val):
                        # Extract year from "2002年" format
                        current_year = int(str(year_val).replace('年', '').strip())

                    # Get month from column 2
                    month_val = row[2]
                    if pd.isna(month_val) or current_year is None:
                        continue

                    try:
                        month = int(float(month_val))
                    except (ValueError, TypeError):
                        continue

                    # Get values
                    total = row[3]  # Total
                    household = row[4]  # Household-related
                    corporate = row[9]  # Corporate-related
                    employment = row[12]  # Employment-related

                    # Convert to float or None
                    def to_float(val):
                        if pd.isna(val):
                            return None
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return None

                    # Create date string
                    date_formatted = f"{current_year}-{month:02d}-01"

                    data_points.append({
                        "date": date_formatted,
                        "total": to_float(total),
                        "household": to_float(household),
                        "corporate": to_float(corporate),
                        "employment": to_float(employment)
                    })

                except (ValueError, AttributeError, IndexError) as e:
                    logger.debug(f"Error parsing row {row_idx}: {e}")
                    continue

            logger.info(f"Parsed {len(data_points)} data points from {data_type} sheet")
            return data_points if data_points else None

        except Exception as e:
            logger.error(f"Error parsing Excel data for {data_type}: {e}", exc_info=True)
            return None

    def _fetch_economy_watcher_data(self) -> Optional[Dict]:
        """
        Fetch Economy Watcher data from Cabinet Office

        Returns:
            Dict containing current and outlook data, last_updated, and source
        """
        try:
            logger.info("Fetching Japan Economy Watcher Survey data")

            # Download Excel file
            excel_content = self._download_excel_file()
            if not excel_content:
                logger.error("Failed to download Excel file")
                return None

            # Parse current conditions (sheet 0)
            current_data = self._parse_sheet_data(excel_content, 0, "current")
            if not current_data:
                logger.error("Failed to parse current conditions data")
                return None

            # Parse outlook (sheet 1)
            outlook_data = self._parse_sheet_data(excel_content, 1, "outlook")
            if not outlook_data:
                logger.error("Failed to parse outlook data")
                return None

            # Sort by date and round values
            def process_data(data_points):
                sorted_data = sorted(data_points, key=lambda x: x['date'])
                processed = []
                for item in sorted_data:
                    processed.append({
                        "date": item['date'],
                        "total": round(item['total'], 1) if item['total'] is not None else None,
                        "household": round(item['household'], 1) if item['household'] is not None else None,
                        "corporate": round(item['corporate'], 1) if item['corporate'] is not None else None,
                        "employment": round(item['employment'], 1) if item['employment'] is not None else None
                    })
                return processed

            processed_current = process_data(current_data)
            processed_outlook = process_data(outlook_data)

            # Get latest data points
            current_latest = processed_current[-1] if processed_current else None
            outlook_latest = processed_outlook[-1] if processed_outlook else None

            return {
                "current": {
                    "data": processed_current,
                    "latest": current_latest
                },
                "outlook": {
                    "data": processed_outlook,
                    "latest": outlook_latest
                },
                "last_updated": datetime.now().isoformat(),
                "source": "Cabinet Office (内閣府)"
            }

        except Exception as e:
            logger.error(f"Error fetching Economy Watcher data: {e}", exc_info=True)
            return None

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get data from Redis cache"""
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return cached
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
        return None

    def _set_to_cache(self, cache_key: str, data: Dict[str, Any]) -> bool:
        """Set data to Redis cache"""
        try:
            redis_client.set(cache_key, data, expire=self.CACHE_TTL)
            return True
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
        return False

    def _get_file_cache(self) -> Optional[Dict[str, Any]]:
        """Get data from file cache"""
        cache_file = self.cache_dir / "economy_watcher_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"File cache read error: {e}")
        return None

    def _set_file_cache(self, data: Dict[str, Any]) -> bool:
        """Set data to file cache"""
        cache_file = self.cache_dir / "economy_watcher_cache.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            logger.warning(f"File cache write error: {e}")
        return False

    def get_economy_watcher_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get Japan Economy Watcher data with caching"""
        # Check cache if not forcing refresh
        if not force_refresh:
            cached_data = self._get_from_cache(self.CACHE_KEY_CURRENT)
            if cached_data:
                cached_data["cached"] = True
                cached_data["cache_source"] = "redis"
                return cached_data

            file_cached = self._get_file_cache()
            if file_cached:
                self._set_to_cache(self.CACHE_KEY_CURRENT, file_cached)
                file_cached["cached"] = True
                file_cached["cache_source"] = "file"
                return file_cached

        # Fetch fresh data
        data = self._fetch_economy_watcher_data()
        if data:
            data["cached"] = False
            self._set_to_cache(self.CACHE_KEY_CURRENT, data)
            self._set_file_cache(data)
            return data

        # Fallback to cache on error
        file_cached = self._get_file_cache()
        if file_cached:
            file_cached["cached"] = True
            file_cached["cache_source"] = "file_fallback"
            file_cached["error"] = "Failed to fetch fresh data, using cached data"
            return file_cached

        return {
            "current": {"data": [], "latest": None},
            "outlook": {"data": [], "latest": None},
            "last_updated": datetime.now().isoformat(),
            "cached": False,
            "error": "Failed to fetch Japan Economy Watcher data"
        }

    def get_current_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get current conditions (現状判断) data only"""
        full_data = self.get_economy_watcher_data(force_refresh)

        current_section = full_data.get("current", {"data": [], "latest": None})

        return {
            "data": current_section.get("data", []),
            "latest": current_section.get("latest"),
            "last_updated": full_data.get("last_updated"),
            "source": full_data.get("source", "Cabinet Office (内閣府)"),
            "cached": full_data.get("cached", False),
            "indicator": "japan_economy_watcher_current"
        }

    def get_outlook_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get outlook (先行き判断) data only"""
        full_data = self.get_economy_watcher_data(force_refresh)

        outlook_section = full_data.get("outlook", {"data": [], "latest": None})

        return {
            "data": outlook_section.get("data", []),
            "latest": outlook_section.get("latest"),
            "last_updated": full_data.get("last_updated"),
            "source": full_data.get("source", "Cabinet Office (内閣府)"),
            "cached": full_data.get("cached", False),
            "indicator": "japan_economy_watcher_outlook"
        }

    def invalidate_cache(self) -> bool:
        """Invalidate all caches"""
        success = True

        try:
            redis_client.delete(self.CACHE_KEY_CURRENT)
            redis_client.delete(self.CACHE_KEY_OUTLOOK)
        except Exception as e:
            logger.warning(f"Redis cache invalidation error: {e}")
            success = False

        cache_file = self.cache_dir / "economy_watcher_cache.json"
        if cache_file.exists():
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"File cache invalidation error: {e}")
                success = False

        return success

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        redis_cached = False
        file_cached = False

        try:
            redis_cached = redis_client.exists(self.CACHE_KEY_CURRENT)
        except:
            pass

        cache_file = self.cache_dir / "economy_watcher_cache.json"
        file_cached = cache_file.exists()

        return {
            "redis_cached": redis_cached,
            "file_cached": file_cached,
            "cache_key": self.CACHE_KEY_CURRENT,
            "cache_ttl_days": self.CACHE_TTL // (60 * 60 * 24)
        }


# Singleton instance
economy_watcher_service = EconomyWatcherService()
