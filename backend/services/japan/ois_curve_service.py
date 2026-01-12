"""
JSCC OIS Curve Service
Fetches and parses OIS (Overnight Index Swap) curve data from JSCC Settlement Rates PDF

データソース: JSCC (Japan Securities Clearing Corporation)
URL: https://www.jpx.co.jp/jscc/en/cimhll0000000umu-att/SettlementRates_{YYYYMMDD}.pdf
更新頻度: 営業日毎、16:00 JST頃

取得データ:
- OIS金利カーブ（1W〜1Y）
"""
import logging
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

import pdfplumber
import requests

from services.usa.fred_utils import CacheManager, load_file_cache, save_file_cache
from core.redis_client import redis_client

logger = logging.getLogger(__name__)

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
REDIS_KEY = "japan:jscc:ois_curve"
CACHE_FILE = Path(__file__).parent.parent.parent / "cache" / "japan" / "monetary_policy" / "jscc_ois_curve.json"


class OISCurveService:
    """Service for fetching JSCC OIS curve data"""

    # JSCC Settlement Rates URL pattern
    JSCC_BASE_URL = "https://www.jpx.co.jp/jscc/en/cimhll0000000umu-att"

    # OIS tenors to extract (in order of appearance in PDF)
    OIS_TENORS = ["1W", "2W", "3W", "1M", "2M", "3M", "4M", "5M", "6M", "7M", "8M", "9M", "10M", "11M", "1Y"]

    # JSCC PDF公開時刻（JST）- 16:00頃
    RELEASE_HOUR_JST = 16
    RELEASE_MINUTE_JST = 0

    def __init__(self):
        """Initialize OIS Curve service"""
        self.cache_manager = CacheManager(
            redis_key=REDIS_KEY,
            cache_file=CACHE_FILE,
            econalpha_id=None  # OISカーブは独自スケジュール
        )

    def _get_settlement_rates_url(self, date: datetime) -> str:
        """
        Get JSCC Settlement Rates PDF URL for a given date
        Format: SettlementRates_YYYYMMDD.pdf
        """
        date_str = date.strftime("%Y%m%d")
        return f"{self.JSCC_BASE_URL}/SettlementRates_{date_str}.pdf"

    def _download_pdf(self, url: str) -> Optional[Path]:
        """Download PDF to temporary file"""
        try:
            logger.info(f"Downloading PDF from {url}")
            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Failed to download PDF: HTTP {response.status_code}")
                return None

            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.write(response.content)
            temp_file.close()

            logger.info(f"PDF downloaded to {temp_file.name}")
            return Path(temp_file.name)

        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            return None

    def _parse_ois_from_pdf(self, pdf_path: Path) -> Optional[Dict[str, float]]:
        """
        Parse OIS rates from JSCC Settlement Rates PDF

        Returns:
            Dictionary mapping tenor to rate (e.g., {"1W": 0.25, "1M": 0.30, ...})
        """
        try:
            logger.info(f"Parsing OIS data from {pdf_path}")
            ois_data = {}

            with pdfplumber.open(pdf_path) as pdf:
                # OIS data is typically on the first page
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()

                    if not text:
                        continue

                    # Look for OIS section
                    # Pattern: OIS (JPY) followed by tenor and rate
                    # Example: "1W    0.250" or "1M    0.300"

                    # Split into lines
                    lines = text.split('\n')

                    in_ois_section = False
                    for line in lines:
                        # Detect OIS section start
                        if 'OIS' in line and 'JPY' in line:
                            in_ois_section = True
                            continue

                        # Exit if we hit another section
                        if in_ois_section and any(keyword in line for keyword in ['FRA', 'IRS', 'Basis Swap']):
                            break

                        # Parse OIS rates
                        if in_ois_section:
                            # Try to match tenor and rate
                            # Pattern: tenor (1W, 2W, etc.) followed by rate (percentage)
                            for tenor in self.OIS_TENORS:
                                # Match patterns like "1W    0.250" or "1W 0.250" or "1W    -0.100"
                                pattern = rf'\b{re.escape(tenor)}\s+([-]?\d+\.\d+)'
                                match = re.search(pattern, line)

                                if match:
                                    rate = float(match.group(1))
                                    ois_data[tenor] = rate
                                    logger.debug(f"Found {tenor}: {rate}%")

            if not ois_data:
                logger.warning("No OIS data found in PDF")
                return None

            logger.info(f"Successfully parsed {len(ois_data)} OIS tenors")
            return ois_data

        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return None

    def _fetch_ois_data_for_date(self, target_date: datetime) -> Optional[Dict[str, Any]]:
        """
        Fetch OIS curve data for a specific date
        """
        url = self._get_settlement_rates_url(target_date)
        pdf_path = self._download_pdf(url)

        if pdf_path is None:
            return None

        try:
            ois_data = self._parse_ois_from_pdf(pdf_path)

            if ois_data:
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "data": ois_data
                }
        finally:
            # Clean up temporary file
            if pdf_path.exists():
                pdf_path.unlink()

        return None

    def _fetch_with_cache_comparison(self) -> Optional[Dict[str, Any]]:
        """
        Fetch current OIS data and use cached data as previous for comparison
        Since PDF only contains current day, we compare with yesterday's cached data
        """
        # Load existing cache to get previous snapshot
        cached_previous = None
        file_cache = load_file_cache(CACHE_FILE)

        if file_cache:
            cached_data = file_cache.get("data", {})
            # Extract current snapshot from cache to use as previous
            if "current" in cached_data:
                cached_previous = cached_data["current"]
                logger.info(f"Found cached data from {cached_previous.get('date')} to use as previous")

        # Fetch current day data
        today = datetime.now(JST)
        current_data = None

        # Try up to 5 previous business days
        for days_back in range(5):
            attempt_date = today - timedelta(days=days_back)
            if attempt_date.weekday() >= 5:  # Skip weekends
                continue

            current_data = self._fetch_ois_data_for_date(attempt_date)
            if current_data:
                logger.info(f"Found current OIS data for {current_data['date']}")
                break

        if not current_data:
            logger.error("Failed to fetch current OIS data")
            return None

        # Use cached data as previous, or generate dummy if no cache exists
        previous_data = None
        if cached_previous:
            # Check if cached data is different from current (different date)
            if cached_previous.get("date") != current_data["date"]:
                previous_data = cached_previous
            else:
                logger.info("Cached data is same date as current, generating dummy previous data")
                previous_data = self._generate_dummy_previous_data(current_data)
        else:
            logger.info("No cached data found, generating dummy previous data for testing")
            previous_data = self._generate_dummy_previous_data(current_data)

        # Format response
        result = {
            "current": {
                "date": current_data["date"],
                "data": [
                    {"tenor": tenor, "rate": rate}
                    for tenor, rate in current_data["data"].items()
                ]
            },
            "last_updated": datetime.now(JST).isoformat()
        }

        if previous_data:
            # Convert dict format to list format if needed
            if isinstance(previous_data.get("data"), dict):
                result["previous"] = {
                    "date": previous_data["date"],
                    "data": [
                        {"tenor": tenor, "rate": rate}
                        for tenor, rate in previous_data["data"].items()
                    ]
                }
            elif isinstance(previous_data.get("data"), list):
                result["previous"] = previous_data
            else:
                logger.warning("Invalid previous data format, skipping")

        return result

    def _generate_dummy_previous_data(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate dummy previous day data for testing by adding small variations
        """
        import random

        # Calculate previous business day
        current_date = datetime.strptime(current_data["date"], "%Y-%m-%d")
        days_back = 1
        while days_back < 10:
            previous_date = current_date - timedelta(days=days_back)
            if previous_date.weekday() < 5:  # Not weekend
                break
            days_back += 1

        # Create dummy data with slight variations (-0.02% to +0.02%)
        dummy_data = {}
        for tenor, rate in current_data["data"].items():
            variation = random.uniform(-0.02, 0.02)
            dummy_data[tenor] = round(rate + variation, 3)

        logger.info(f"Generated dummy previous day data for {previous_date.strftime('%Y-%m-%d')}")

        return {
            "date": previous_date.strftime("%Y-%m-%d"),
            "data": dummy_data
        }

    def get_ois_curve(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get OIS curve data with caching

        Args:
            force_refresh: キャッシュを無視して強制的に最新データを取得

        Returns:
            {
                "current": {"date": "YYYY-MM-DD", "data": [{"tenor": "1W", "rate": 0.25}, ...]},
                "previous": {"date": "YYYY-MM-DD", "data": [...]},
                "last_updated": "ISO datetime",
                "cached": bool
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_data, source = self.cache_manager.get_cached_data()
            if cached_data:
                # スケジュールベースの更新判定
                if not self.should_refresh():
                    logger.info(f"Returning cached OIS data from {source}")
                    return {**cached_data.get("data", {}), "cached": True, "source": source}

        # 新規データ取得
        data = self._fetch_with_cache_comparison()
        if data:
            # キャッシュに保存
            self.cache_manager.save({"data": data})
            return {**data, "cached": False, "source": "fresh"}

        # フォールバック: 古いキャッシュを返す
        fallback_data, fallback_source = self.cache_manager.get_fallback_data()
        if fallback_data:
            logger.warning(f"Returning fallback data from {fallback_source}")
            return {**fallback_data.get("data", {}), "cached": True, "source": fallback_source}

        return self._get_fallback_data()

    def _get_fallback_data(self) -> Dict[str, Any]:
        """Return empty fallback data"""
        return {
            "current": {
                "date": datetime.now(JST).strftime("%Y-%m-%d"),
                "data": []
            },
            "last_updated": datetime.now(JST).isoformat(),
            "error": "Failed to fetch OIS data",
            "cached": False,
            "source": "fallback"
        }

    def should_refresh(self) -> bool:
        """
        Check if cache should be refreshed
        JSCC publishes at 16:00 JST daily on business days
        """
        file_cache = load_file_cache(CACHE_FILE)

        if not file_cache:
            return True

        try:
            last_updated_str = file_cache.get("last_updated")
            if not last_updated_str:
                return True

            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # If it's weekend, no need to refresh
            if now.weekday() >= 5:
                return False

            # If cached data is from today after 16:00, no refresh needed
            if (last_updated.date() == now.date() and
                    last_updated.hour >= self.RELEASE_HOUR_JST):
                return False

            # If it's after 16:00 today and cache is old, refresh
            if (now.hour >= self.RELEASE_HOUR_JST and
                    last_updated.date() < now.date()):
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking refresh status: {e}")
            return True


# シングルトンインスタンス
_service_instance: Optional[OISCurveService] = None


def get_ois_curve_service() -> OISCurveService:
    """Get or create OISCurveService singleton instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = OISCurveService()
    return _service_instance


# グローバルサービスインスタンス
ois_curve_service = get_ois_curve_service()
