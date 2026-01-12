"""
GDPデフレーターサービス（e-Stat API）

データソース: e-Stat（内閣府）
statsDataId: 0003113635
TAB_CODE: 12 (前年同期比)
CAT01_CODE: 11 (国内総生産・支出側)

キャッシュ方式: Redis + ファイルフォールバック
"""
import json
import logging
import os
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "gdp_deflator_cache.json"


class GDPDeflatorService:
    """GDPデフレーター（前年同期比）サービス"""

    # e-Stat API endpoint and statistics data ID
    ESTAT_API_URL = "http://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    STATS_DATA_ID = "0003113635"  # 国内総生産デフレーター

    # Filter codes for the data we want
    TAB_CODE_YOY = "12"  # 前年同期比 (Year-over-Year)
    CAT01_CODE_GDP = "11"  # 国内総生産(支出側)

    DATA_CACHE_KEY = "japan:gdp_deflator:data"

    def __init__(self):
        """Initialize GDP Deflator service"""
        self.api_key = os.getenv('ESTAT_API_KEY')
        if not self.api_key:
            logger.warning("ESTAT_API_KEY not found in environment variables")

    def _fetch_from_estat_api(self) -> Optional[Dict]:
        """
        Fetch GDP deflator data from e-Stat API

        Returns:
            Raw API response data
        """
        try:
            if not self.api_key:
                logger.error("e-Stat API key not configured")
                return None

            logger.info(f"Fetching GDP deflator data from e-Stat API (statsDataId: {self.STATS_DATA_ID})")

            params = {
                "appId": self.api_key,
                "lang": "J",
                "statsDataId": self.STATS_DATA_ID,
                "metaGetFlg": "Y",
                "cntGetFlg": "N",
                "explanationGetFlg": "Y",
                "annotationGetFlg": "Y",
                "sectionHeaderFlg": "1",
                "replaceSpChars": "0",
                # Filter for 前年同期比 (Year-over-Year) and GDP
                "cdTab": self.TAB_CODE_YOY,
                "cdCat01": self.CAT01_CODE_GDP,
            }

            response = requests.get(self.ESTAT_API_URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            logger.info("Successfully fetched GDP deflator data from e-Stat API")

            return data

        except requests.RequestException as e:
            logger.error(f"Error fetching GDP deflator data from e-Stat API: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in e-Stat API fetch: {e}")
            return None

    def _parse_estat_response(self, api_data: Dict) -> List[Dict[str, Any]]:
        """
        Parse e-Stat API response and convert to structured data

        Args:
            api_data: Raw API response

        Returns:
            List of data points with date and value
        """
        try:
            logger.info("Parsing e-Stat API response for GDP deflator")

            if 'GET_STATS_DATA' not in api_data:
                logger.error("Invalid API response structure")
                return []

            stats_data = api_data['GET_STATS_DATA']

            if 'STATISTICAL_DATA' not in stats_data:
                logger.error("No statistical data in response")
                return []

            stat_data = stats_data['STATISTICAL_DATA']

            # Extract data values
            if 'DATA_INF' not in stat_data or 'VALUE' not in stat_data['DATA_INF']:
                logger.error("No data values in response")
                return []

            values = stat_data['DATA_INF']['VALUE']
            if not isinstance(values, list):
                values = [values]

            logger.info(f"Found {len(values)} raw data points for GDP deflator")

            # Process values
            series_data = []
            for val in values:
                try:
                    # Extract time code
                    time_code = val.get('@time', '')
                    if not time_code:
                        continue

                    # Parse time code to quarter format
                    year = int(time_code[:4])
                    month_range = time_code[4:]

                    # Map month range to quarter
                    if month_range == "000103":
                        quarter = "Q1"
                    elif month_range == "000406":
                        quarter = "Q2"
                    elif month_range == "000709":
                        quarter = "Q3"
                    elif month_range == "001012":
                        quarter = "Q4"
                    else:
                        logger.debug(f"Unknown month range: {month_range}")
                        continue

                    # Get value
                    value_str = val.get('$', '')
                    if not value_str or value_str == '-':
                        continue

                    # Remove % sign and convert to float
                    value_str = value_str.replace('%', '').strip()
                    try:
                        value = float(value_str)
                    except ValueError:
                        logger.debug(f"Could not convert value to float: {value_str}")
                        continue

                    # Create date string in YYYY-QX format
                    date_str = f"{year}-{quarter}"

                    series_data.append({
                        "date": date_str,
                        "value": round(value, 2)
                    })

                except Exception as e:
                    logger.debug(f"Error processing value: {e}")
                    continue

            # Sort by date
            series_data.sort(key=lambda x: (int(x["date"][:4]), x["date"][5:]))

            # Filter to data from 1995 onwards
            if series_data:
                cutoff_date = "1995-Q1"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            logger.info(f"Processed GDP deflator data: {len(series_data)} data points")
            return series_data

        except Exception as e:
            logger.error(f"Error parsing e-Stat response: {e}", exc_info=True)
            return []

    def get_gdp_deflator_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get GDP deflator data with caching

        Args:
            force_refresh: Force refresh from source

        Returns:
            GDP deflator data dictionary
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                data = cached_data.get("data", [])
                return {
                    "data": data,
                    "latest": data[-1] if data else None,
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # e-Stat APIからデータ取得
        api_data = self._fetch_from_estat_api()
        if api_data:
            parsed_data = self._parse_estat_response(api_data)
            if parsed_data:
                cache_payload = {
                    "data": parsed_data,
                    "last_updated": datetime.now(JST).isoformat()
                }
                redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                self._save_file_cache(cache_payload)

                return {
                    "data": parsed_data,
                    "latest": parsed_data[-1] if parsed_data else None,
                    "cached": False,
                    "source": "e-stat",
                    "last_updated": datetime.now(JST).isoformat()
                }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
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

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """Load from file cache"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """Save to file cache"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """Invalidate Redis cache"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "GDP Deflator (YoY)",
            "source": "e-Stat (Cabinet Office)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# Singleton instance
gdp_deflator_service = GDPDeflatorService()
