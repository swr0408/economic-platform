"""
BOJ Consumption Activity Index (CAI) Service
Fetches monthly consumption activity index data from Bank of Japan

Data includes:
- Nominal Consumption Activity Index (名目消費活動指数)
- Real Consumption Activity Index (実質消費活動指数)

Source: Bank of Japan
URL: https://www.boj.or.jp/research/research_data/cai/cai.xlsx
Sheet: Data1 (Monthly data)

Publication schedule:
- 5th business day of each month at 14:00 JST (原則として毎月第5営業日)
- May be delayed due to operational reasons
"""
import io
import json
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from backend.core.redis_client import redis_client
except ImportError:
    from core.redis_client import redis_client

try:
    import jpholiday
    HAS_JPHOLIDAY = True
except ImportError:
    HAS_JPHOLIDAY = False

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class BOJCAIService:
    """Service for fetching BOJ Consumption Activity Index data"""

    # BOJ CAI Excel file URL
    BOJ_CAI_URL = "https://www.boj.or.jp/research/research_data/cai/cai.xlsx"
    SHEET_NAME = "Data1"  # Monthly data sheet

    # Cache settings
    CACHE_KEY = "japan:boj_cai:data"
    CACHE_TTL = 60 * 60 * 24 * 7  # 7 days

    # File cache
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "consumption"

    def __init__(self):
        """Initialize BOJ CAI service"""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._last_data_date: Optional[str] = None

    def _is_business_day(self, date: datetime) -> bool:
        """
        Check if a date is a business day (not weekend or Japanese holiday)

        Args:
            date: Date to check

        Returns:
            True if business day, False otherwise
        """
        # Check if weekend (Saturday=5, Sunday=6)
        if date.weekday() >= 5:
            return False

        # Check if Japanese holiday
        if HAS_JPHOLIDAY and jpholiday.is_holiday(date):
            return False

        return True

    def _get_nth_business_day(self, year: int, month: int, n: int) -> datetime:
        """
        Get the nth business day of a given month

        Args:
            year: Year
            month: Month
            n: Which business day (1 for first, 2 for second, etc.)

        Returns:
            Date of the nth business day
        """
        # Start from first day of month
        current_date = datetime(year, month, 1)
        business_days_count = 0

        # Iterate through days of the month
        while current_date.month == month:
            if self._is_business_day(current_date):
                business_days_count += 1
                if business_days_count == n:
                    return current_date
            current_date += timedelta(days=1)

        # If we couldn't find nth business day in the month, return last day
        return current_date - timedelta(days=1)

    def _should_refresh(self, last_updated_str: Optional[str] = None) -> bool:
        """
        Check if cache should be refreshed.

        BOJ CAI is published on the 5th business day of each month at 14:00 JST.
        Refresh strategy:
        - If cache age >= 7 days: refresh (covers normal monthly cadence + publication delays).
        - If today is on/after the 5th business day of this month AND cache hasn't been
          updated since that day: refresh (catches the regular monthly release without
          requiring requests to land in a 30-minute window).

        Args:
            last_updated_str: ISO format string of last update time

        Returns:
            True if should refresh, False otherwise
        """
        if not last_updated_str:
            return True

        try:
            last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
        except Exception as e:
            logger.warning(f"Error parsing last_updated: {e}")
            return True

        now = datetime.now(JST)
        cache_age_days = (now - last_updated).total_seconds() / 86400

        # 7-day TTL regardless of publication schedule
        if cache_age_days >= 7:
            return True

        # Refresh once after the monthly publication (5th business day, 14:00 JST)
        fifth_bd = self._get_nth_business_day(now.year, now.month, 5)
        fifth_bd_release = fifth_bd.replace(hour=14, minute=0, tzinfo=JST)
        if now >= fifth_bd_release and last_updated < fifth_bd_release:
            return True

        return False

    def _download_excel_file(self) -> Optional[bytes]:
        """
        Download CAI Excel file from BOJ

        Returns:
            Excel file content as bytes, or None if failed
        """
        try:
            logger.info(f"Downloading BOJ CAI data from {self.BOJ_CAI_URL}")

            response = requests.get(
                self.BOJ_CAI_URL,
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            response.raise_for_status()

            logger.info(f"Successfully downloaded {len(response.content)} bytes")
            return response.content

        except Exception as e:
            logger.error(f"Error downloading BOJ CAI data: {e}")
            return None

    def _parse_excel_data(self, excel_content: bytes) -> Optional[List[Dict]]:
        """
        Parse CAI data from Excel file

        Excel structure (Data1 sheet):
        - Row 0-4: Headers
        - Row 5+: Data
        - Column 0: Date (datetime)
        - Column 1: Nominal CAI
        - Column 2: Real CAI

        Args:
            excel_content: Excel file content as bytes

        Returns:
            List of data points with date, nominal, and real values
        """
        try:
            logger.info("Parsing BOJ CAI Excel file")

            # Read Excel file
            df = pd.read_excel(
                io.BytesIO(excel_content),
                sheet_name=self.SHEET_NAME,
                header=None,
                engine='openpyxl'
            )

            logger.info(f"Excel shape: {df.shape}")

            result = []

            # Data starts from row 5 (index 5)
            for idx in range(5, len(df)):
                try:
                    row = df.iloc[idx]

                    # Get date from column 0
                    date_val = row[0]
                    if pd.isna(date_val):
                        continue

                    # Parse date
                    if isinstance(date_val, datetime):
                        date_str = date_val.strftime("%Y-%m-%d")
                    else:
                        date_str = str(date_val)[:10]  # Take YYYY-MM-DD part

                    # Get nominal CAI (column 1)
                    nominal_val = row[1]
                    nominal_cai = round(float(nominal_val), 2) if pd.notna(nominal_val) else None

                    # Get real CAI (column 2)
                    real_val = row[2]
                    real_cai = round(float(real_val), 2) if pd.notna(real_val) else None

                    # Only add if we have at least one value
                    if nominal_cai is not None or real_cai is not None:
                        result.append({
                            "date": date_str,
                            "nominal_cai": nominal_cai,
                            "real_cai": real_cai
                        })

                except Exception as e:
                    logger.debug(f"Error processing row {idx}: {e}")
                    continue

            logger.info(f"Parsed {len(result)} data points from BOJ CAI")

            if result:
                logger.info(f"Date range: {result[0]['date']} to {result[-1]['date']}")

            return result

        except Exception as e:
            logger.error(f"Error parsing BOJ CAI Excel: {e}", exc_info=True)
            return None

    def _fetch_cai_data(self) -> Optional[Dict[str, Any]]:
        """
        Fetch BOJ CAI data from source

        Returns:
            CAI data dictionary
        """
        try:
            # Download Excel file
            excel_content = self._download_excel_file()
            if not excel_content:
                return None

            # Parse Excel
            data_points = self._parse_excel_data(excel_content)
            if not data_points:
                return None

            # Sort by date
            data_points.sort(key=lambda x: x['date'])

            # Get latest data point
            latest = data_points[-1] if data_points else None

            return {
                "data": data_points,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Bank of Japan",
                "indicator": "Consumption Activity Index (CAI)"
            }

        except Exception as e:
            logger.error(f"Error fetching BOJ CAI data: {e}", exc_info=True)
            return None

    def _get_from_cache(self) -> Optional[Dict[str, Any]]:
        """Get data from Redis cache"""
        try:
            cached = redis_client.get(self.CACHE_KEY)
            if cached:
                return cached
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
        return None

    def _set_to_cache(self, data: Dict[str, Any]) -> bool:
        """Set data to Redis cache"""
        try:
            redis_client.set(self.CACHE_KEY, data, expire=self.CACHE_TTL)
            return True
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
        return False

    def _get_file_cache(self) -> Optional[Dict[str, Any]]:
        """Get data from file cache"""
        cache_file = self.CACHE_DIR / "boj_cai_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"File cache read error: {e}")
        return None

    def _set_file_cache(self, data: Dict[str, Any]) -> bool:
        """Set data to file cache"""
        cache_file = self.CACHE_DIR / "boj_cai_cache.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.warning(f"File cache write error: {e}")
        return False

    def get_cai_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get BOJ CAI data with caching

        Args:
            force_refresh: Force refresh from source

        Returns:
            CAI data dictionary
        """
        # Check cache if not forcing refresh
        if not force_refresh:
            cached_data = self._get_from_cache()
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if not self._should_refresh(last_updated_str):
                    cached_data["cached"] = True
                    cached_data["source"] = "redis"
                    return cached_data

            # Try file cache
            file_cached = self._get_file_cache()
            if file_cached:
                last_updated_str = file_cached.get("last_updated")
                if not self._should_refresh(last_updated_str):
                    self._set_to_cache(file_cached)
                    file_cached["cached"] = True
                    file_cached["source"] = "file"
                    return file_cached

        # Fetch fresh data
        data = self._fetch_cai_data()
        if data:
            data["cached"] = False
            self._set_to_cache(data)
            self._set_file_cache(data)
            return data

        # Fallback to cache on error
        file_cached = self._get_file_cache()
        if file_cached:
            file_cached["cached"] = True
            file_cached["source"] = "file_fallback"
            file_cached["error"] = "Failed to fetch fresh data, using cached data"
            return file_cached

        return {
            "data": [],
            "latest": None,
            "last_updated": datetime.now(JST).isoformat(),
            "cached": False,
            "error": "Failed to fetch BOJ CAI data"
        }

    def get_chart_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get CAI data formatted for chart display"""
        raw_data = self.get_cai_data(force_refresh)

        if "error" in raw_data and not raw_data.get("data"):
            return raw_data

        data_points = raw_data.get("data", [])

        # Sort by date ascending for chart
        sorted_data = sorted(data_points, key=lambda x: x["date"])

        return {
            "data": sorted_data,
            "metadata": {
                "title": "消費活動指数（旅行収支調整前）",
                "source": "日本銀行",
                "unit": "指数（2015年=100）",
                "series": [
                    {"key": "nominal_cai", "name": "名目消費活動指数", "color": "#1890ff"},
                    {"key": "real_cai", "name": "実質消費活動指数", "color": "#52c41a"},
                ]
            },
            "latest": raw_data.get("latest"),
            "last_updated": raw_data.get("last_updated"),
            "cached": raw_data.get("cached", False),
            "source": raw_data.get("source", "unknown")
        }

    def invalidate_cache(self) -> bool:
        """Invalidate all caches"""
        success = True

        try:
            redis_client.delete(self.CACHE_KEY)
        except Exception as e:
            logger.warning(f"Redis cache invalidation error: {e}")
            success = False

        cache_file = self.CACHE_DIR / "boj_cai_cache.json"
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
            redis_cached = redis_client.exists(self.CACHE_KEY)
        except:
            pass

        cache_file = self.CACHE_DIR / "boj_cai_cache.json"
        file_cached = cache_file.exists()

        return {
            "indicator": "BOJ Consumption Activity Index",
            "redis_cached": redis_cached,
            "file_cached": file_cached,
            "cache_key": self.CACHE_KEY,
            "cache_ttl_days": self.CACHE_TTL // (60 * 60 * 24)
        }


# Singleton instance
boj_cai_service = BOJCAIService()
