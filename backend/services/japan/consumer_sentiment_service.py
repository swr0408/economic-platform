"""
Japan Consumer Sentiment Service
Fetches consumer attitude index data (消費動向調査) from e-Stat Excel files

This service automatically discovers the latest statInfId using e-Stat Data Catalog API.
If API discovery fails, it falls back to a hardcoded list of known statInfIds.

Data items:
- cci: Consumer Confidence Index (消費者態度指数)
- livelihood: Overall livelihood (暮らし向き)
- income: Income growth (収入の増え方)
- employment: Employment environment (雇用環境)
- durable_goods: Willingness to buy durable goods (耐久消費財の買い時判断)

Source: Cabinet Office, Economic and Social Research Institute (e-Stat)
Release: Monthly, around end of month
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
    from backend.services.estat_catalog_service import get_estat_catalog_service
    from backend.services.estat_config import get_survey_config
except ImportError:
    from core.redis_client import redis_client
    from services.estat_catalog_service import get_estat_catalog_service
    from services.estat_config import get_survey_config

logger = logging.getLogger(__name__)


class ConsumerSentimentService:
    """Service for fetching Japan consumer sentiment data from e-Stat Excel files"""

    # Cache settings
    CACHE_KEY = "japan:consumer_sentiment"
    CACHE_TTL = 60 * 60 * 24 * 7  # 7 days

    # e-Stat Excel File Download URL
    ESTAT_EXCEL_URL = "https://www.e-stat.go.jp/stat-search/file-download"

    # Table name filter for finding correct table
    # We want: 長期時系列表（消費者態度指数）1-1 季節調整値
    TABLE_NAME_FILTER = "長期時系列表（消費者態度指数）"

    # Fallback list of statInfIds (used if API discovery fails)
    # Most recent first - 長期時系列表（消費者態度指数）1-1 季節調整値
    FALLBACK_STAT_INF_IDS = [
        "000040396250",  # December 2025 (published 2026-01-08)
        "000040383608",  # November 2025
        "000040371171",  # October 2025
        "000040356629",  # September 2025
    ]

    def __init__(self):
        """Initialize Consumer Sentiment service"""
        self.cache_dir = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "consumer_sentiment"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_service = get_estat_catalog_service()
        try:
            self.config = get_survey_config("consumer_sentiment")
        except KeyError:
            self.config = {
                "survey_code": "00100405",
                "file_kind": "0"
            }

    def _get_download_urls(self) -> List[Dict]:
        """
        Get list of Excel download URLs from e-Stat Data Catalog API

        Returns:
            List of dicts with url, table_name, release_date, format
        """
        try:
            logger.info("Attempting to discover download URLs from e-Stat Data Catalog API")
            urls = self.catalog_service.get_excel_download_urls(
                survey_code=self.config["survey_code"],
                limit=20,
                table_name_filter=self.TABLE_NAME_FILTER
            )

            if urls:
                logger.info(f"Discovered {len(urls)} download URLs from API")
                for url_info in urls[:3]:
                    logger.info(f"  - {url_info.get('table_name', 'unknown')}: {url_info.get('release_date', 'unknown')}")
            else:
                logger.warning("No download URLs discovered from API")

            return urls

        except Exception as e:
            logger.warning(f"Error discovering download URLs from API: {e}")
            return []

    def _get_stat_inf_ids(self) -> List[str]:
        """
        Get list of statInfIds to try, combining API discovery with fallback list

        Returns:
            List of statInfIds, with API-discovered IDs first, then fallback IDs
        """
        stat_inf_ids = []

        # Try to get latest IDs from e-Stat Data Catalog API
        try:
            # Get URLs and extract statInfIds
            urls = self._get_download_urls()
            for url_info in urls:
                stat_inf_id = self.catalog_service.extract_stat_inf_id_from_url(url_info.get("url", ""))
                if stat_inf_id and stat_inf_id not in stat_inf_ids:
                    stat_inf_ids.append(stat_inf_id)

            if stat_inf_ids:
                logger.info(f"Extracted {len(stat_inf_ids)} statInfIds from API URLs: {stat_inf_ids[:3]}...")
            else:
                logger.warning("No statInfIds extracted from API URLs, will use fallback list only")

        except Exception as e:
            logger.warning(f"Error discovering statInfIds from API: {e}, will use fallback list")

        # Add fallback IDs (avoiding duplicates)
        for fallback_id in self.FALLBACK_STAT_INF_IDS:
            if fallback_id not in stat_inf_ids:
                stat_inf_ids.append(fallback_id)

        logger.info(f"Total {len(stat_inf_ids)} statInfIds to try")
        return stat_inf_ids

    def _download_excel_file(self) -> Optional[bytes]:
        """
        Download the Excel file from e-Stat

        First attempts to discover latest download URLs via API, then falls back to statInfIds.

        Returns:
            Excel file content as bytes
        """
        last_error = None

        # First, try direct download URLs from API
        try:
            urls = self._get_download_urls()
            for url_info in urls:
                url = url_info.get("url", "")
                if not url:
                    continue

                try:
                    logger.info(f"Attempting direct download: {url_info.get('table_name', 'unknown')} ({url_info.get('release_date', 'unknown')})")
                    response = requests.get(url, timeout=60)

                    if response.status_code == 200 and len(response.content) > 1000:
                        logger.info(f"Successfully downloaded Excel file directly ({len(response.content)} bytes)")
                        return response.content
                    else:
                        logger.warning(f"Direct download returned HTTP {response.status_code} or invalid content, trying next...")
                        last_error = f"HTTP {response.status_code}"

                except Exception as e:
                    logger.warning(f"Error with direct download: {e}, trying next...")
                    last_error = str(e)

        except Exception as e:
            logger.warning(f"Error getting download URLs: {e}")

        # Fallback: Try statInfId-based download
        logger.info("Falling back to statInfId-based download")
        stat_inf_ids = self._get_stat_inf_ids()

        if not stat_inf_ids:
            logger.error("No statInfIds available to try")
            return None

        # Try each statInfId in order (most recent first)
        for stat_inf_id in stat_inf_ids:
            try:
                params = {
                    "statInfId": stat_inf_id,
                    "fileKind": "0"
                }

                logger.info(f"Attempting to download Excel file (statInfId: {stat_inf_id})")
                response = requests.get(
                    self.ESTAT_EXCEL_URL,
                    params=params,
                    timeout=60
                )

                if response.status_code == 200 and len(response.content) > 1000:
                    logger.info(f"Successfully downloaded Excel file using statInfId: {stat_inf_id} ({len(response.content)} bytes)")
                    return response.content
                else:
                    logger.warning(f"statInfId {stat_inf_id} returned HTTP {response.status_code}, trying next...")
                    last_error = f"HTTP {response.status_code}"

            except Exception as e:
                logger.warning(f"Error with statInfId {stat_inf_id}: {e}, trying next...")
                last_error = str(e)

        # If all IDs failed
        logger.error(f"Failed to download Excel file with any method. Last error: {last_error}")
        return None

    def _parse_date_code(self, date_code: str) -> Optional[str]:
        """
        Parse date code from Excel file (format: YYYYMMDD format like 2025000909 = 2025年9月)

        Args:
            date_code: Date code string from Excel (e.g., "2025000909")

        Returns:
            Date string in YYYY-MM-01 format
        """
        try:
            if not date_code or len(date_code) != 10:
                return None

            year = int(date_code[0:4])
            month = int(date_code[6:8])

            return f"{year}-{month:02d}-01"
        except (ValueError, IndexError):
            return None

    def _parse_excel_data(self, excel_content: bytes) -> Optional[List[Dict]]:
        """
        Parse consumer sentiment data from Excel file

        Excel structure:
        - Sheet: First sheet (seasonally adjusted)
        - Row 6+: Data starts from row 6 (index 6)
        - Column 0: Date code (YYYYMMDD format)
        - Column 4: Consumer Confidence Index (消費者態度指数)
        - Column 6: Overall livelihood (暮らし向き)
        - Column 8: Income growth (収入の増え方)
        - Column 10: Employment (雇用環境)
        - Column 12: Willingness to buy durable goods (耐久消費財の買い時判断)

        Args:
            excel_content: Excel file content as bytes

        Returns:
            List of data points
        """
        try:
            # Read Excel file
            excel_file = io.BytesIO(excel_content)
            df = pd.read_excel(excel_file, sheet_name=0, header=None, engine='openpyxl')

            logger.info(f"Excel shape: {df.shape}")

            # Parse data points (starts from row 6)
            data_points = []

            for row_idx in range(6, len(df)):
                try:
                    row = df.iloc[row_idx]

                    # Get date code from column 0
                    date_code = str(row[0])
                    if pd.isna(row[0]) or date_code == 'nan':
                        continue

                    # Parse date
                    date_formatted = self._parse_date_code(date_code)
                    if not date_formatted:
                        continue

                    # Get values
                    cci = row[4]  # Consumer Confidence Index
                    livelihood = row[6]  # Overall livelihood
                    income = row[8]  # Income growth
                    employment = row[10]  # Employment
                    durable_goods = row[12]  # Willingness to buy durable goods

                    # Convert to float or None
                    def to_float(val):
                        if pd.isna(val):
                            return None
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return None

                    data_points.append({
                        "date": date_formatted,
                        "cci": to_float(cci),
                        "livelihood": to_float(livelihood),
                        "income": to_float(income),
                        "employment": to_float(employment),
                        "durable_goods": to_float(durable_goods)
                    })

                except (ValueError, AttributeError, IndexError) as e:
                    logger.debug(f"Error parsing row {row_idx}: {e}")
                    continue

            logger.info(f"Parsed {len(data_points)} data points from Excel")
            return data_points if data_points else None

        except Exception as e:
            logger.error(f"Error parsing Excel data: {e}", exc_info=True)
            return None

    def _fetch_consumer_sentiment_data(self) -> Optional[Dict]:
        """
        Fetch consumer sentiment data from e-Stat Excel file

        Returns:
            Dict containing data, last_updated, and source
        """
        try:
            logger.info("Fetching Japan consumer sentiment data from e-Stat Excel")

            # Download Excel file
            excel_content = self._download_excel_file()
            if not excel_content:
                logger.error("Failed to download Excel file")
                return None

            # Parse Excel data
            data_points = self._parse_excel_data(excel_content)
            if not data_points:
                logger.error("Failed to parse Excel data")
                return None

            # Sort by date and round values
            sorted_data = sorted(data_points, key=lambda x: x['date'])

            processed_data = []
            for item in sorted_data:
                processed_data.append({
                    "date": item['date'],
                    "cci": round(item['cci'], 1) if item['cci'] is not None else None,
                    "livelihood": round(item['livelihood'], 1) if item['livelihood'] is not None else None,
                    "income": round(item['income'], 1) if item['income'] is not None else None,
                    "employment": round(item['employment'], 1) if item['employment'] is not None else None,
                    "durable_goods": round(item['durable_goods'], 1) if item['durable_goods'] is not None else None
                })

            # Get latest data point
            latest = processed_data[-1] if processed_data else None

            return {
                "data": processed_data,
                "latest": latest,
                "last_updated": datetime.now().isoformat(),
                "source": "Cabinet Office, Economic and Social Research Institute (e-Stat)"
            }

        except Exception as e:
            logger.error(f"Error fetching consumer sentiment data: {e}", exc_info=True)
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
        cache_file = self.cache_dir / "consumer_sentiment_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"File cache read error: {e}")
        return None

    def _set_file_cache(self, data: Dict[str, Any]) -> bool:
        """Set data to file cache"""
        cache_file = self.cache_dir / "consumer_sentiment_cache.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            logger.warning(f"File cache write error: {e}")
        return False

    def get_consumer_sentiment_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get Japan consumer sentiment data with caching"""
        # Check cache if not forcing refresh
        if not force_refresh:
            cached_data = self._get_from_cache()
            if cached_data:
                cached_data["cached"] = True
                cached_data["source"] = "redis"
                return cached_data

            file_cached = self._get_file_cache()
            if file_cached:
                self._set_to_cache(file_cached)
                file_cached["cached"] = True
                file_cached["source"] = "file"
                return file_cached

        # Fetch fresh data
        data = self._fetch_consumer_sentiment_data()
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
            "last_updated": datetime.now().isoformat(),
            "cached": False,
            "error": "Failed to fetch Japan consumer sentiment data"
        }

    def get_chart_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get consumer sentiment data formatted for chart display"""
        raw_data = self.get_consumer_sentiment_data(force_refresh)

        if "error" in raw_data and not raw_data.get("data"):
            return raw_data

        data_points = raw_data.get("data", [])

        # Sort by date ascending for chart
        sorted_data = sorted(data_points, key=lambda x: x["date"])

        return {
            "data": sorted_data,
            "metadata": {
                "title": "消費動向調査（消費者態度指数）",
                "source": "内閣府経済社会総合研究所",
                "unit": "ポイント",
                "series": [
                    {"key": "cci", "name": "消費者態度指数", "color": "#1890ff"},
                    {"key": "livelihood", "name": "暮らし向き", "color": "#52c41a"},
                    {"key": "income", "name": "収入の増え方", "color": "#faad14"},
                    {"key": "employment", "name": "雇用環境", "color": "#722ed1"},
                    {"key": "durable_goods", "name": "耐久消費財の買い時判断", "color": "#eb2f96"}
                ]
            },
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

        cache_file = self.cache_dir / "consumer_sentiment_cache.json"
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

        cache_file = self.cache_dir / "consumer_sentiment_cache.json"
        file_cached = cache_file.exists()

        return {
            "redis_cached": redis_cached,
            "file_cached": file_cached,
            "cache_key": self.CACHE_KEY,
            "cache_ttl_days": self.CACHE_TTL // (60 * 60 * 24)
        }


# Singleton instance
consumer_sentiment_service = ConsumerSentimentService()
