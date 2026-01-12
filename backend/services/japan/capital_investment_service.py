"""
設備投資サービス（Capital Investment）

データソース: e-Stat（財務省・法人企業統計調査）
statsDataId: 0003060191
CAT01_CODE: 040 (設備投資・当期末新設固定資産合計)
CAT02_CODE: 104 (全産業・除く金融保険業)
CAT03_CODE: 26 (全規模)

キャッシュ方式: Redis + ファイルフォールバック
発表: 3月、6月、9月、12月の1日〜5日頃
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
DATA_CACHE_FILE = CACHE_DIR / "capital_investment_cache.json"


class CapitalInvestmentService:
    """設備投資サービス"""

    # e-Stat API settings
    STATS_DATA_ID = "0003060191"  # 法人企業統計調査 時系列データ
    CAT01_CODE = "040"  # 設備投資(当期末新設固定資産合計)
    CAT02_CODE = "104"  # 全産業（除く金融保険業）
    CAT03_CODE = "26"   # 全規模

    DATA_CACHE_KEY = "japan:capital_investment:data"

    def __init__(self):
        """Initialize the service"""
        self.api_key = os.getenv('ESTAT_API_KEY')

    def _fetch_from_estat(self) -> Optional[Dict[str, Any]]:
        """
        Fetch capital investment data from e-Stat API

        Returns:
            Raw e-Stat API response or None if failed
        """
        if not self.api_key:
            logger.error("ESTAT_API_KEY environment variable not set")
            return None

        url = "http://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

        params = {
            'appId': self.api_key,
            'lang': 'J',
            'statsDataId': self.STATS_DATA_ID,
            'cdCat01': self.CAT01_CODE,
            'cdCat02': self.CAT02_CODE,
            'cdCat03': self.CAT03_CODE,
        }

        try:
            logger.info("Fetching capital investment data from e-Stat...")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'GET_STATS_DATA' not in data:
                logger.error(f"Unexpected response structure: {data}")
                return None

            result = data['GET_STATS_DATA']['RESULT']
            if result.get('STATUS') != 0:
                logger.error(f"e-Stat API error: {result.get('ERROR_MSG')}")
                return None

            logger.info("Successfully fetched data from e-Stat")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch from e-Stat: {e}")
            return None

    def _parse_estat_data(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse raw e-Stat data into structured format

        Args:
            raw_data: Raw data from e-Stat API

        Returns:
            List of dictionaries with date, value, and growth rates
        """
        try:
            values = raw_data['GET_STATS_DATA']['STATISTICAL_DATA']['DATA_INF']['VALUE']

            if not isinstance(values, list):
                values = [values]

            parsed_data = []

            for item in values:
                time_code = item.get('@time', '')
                value_str = item.get('$', '')

                if not time_code or not value_str:
                    continue

                # Parse time code (e.g., "20241" -> 2024-Q1)
                try:
                    year = int(time_code[:4])
                    quarter = int(time_code[4:])
                except (ValueError, IndexError):
                    continue

                date_str = f"{year}-Q{quarter}"

                try:
                    value = float(value_str)
                    parsed_data.append({
                        'date': date_str,
                        'value': value,
                        'unit': '百万円',
                        '_year': year,
                        '_quarter': quarter
                    })
                except ValueError:
                    continue

            # Sort by year and quarter
            parsed_data.sort(key=lambda x: (x['_year'], x['_quarter']))

            # Remove temporary sorting fields
            for item in parsed_data:
                del item['_year']
                del item['_quarter']

            logger.info(f"Parsed {len(parsed_data)} data points from e-Stat")
            return parsed_data

        except Exception as e:
            logger.error(f"Error parsing e-Stat data: {e}")
            return []

    def _calculate_growth_rates(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate QoQ and YoY growth rates

        Args:
            data: List of capital investment data

        Returns:
            List with growth rates added
        """
        result = []

        for i, item in enumerate(data):
            new_item = item.copy()

            # QoQ growth (previous quarter)
            if i > 0:
                prev_value = data[i - 1]['value']
                current_value = item['value']
                if prev_value and prev_value != 0:
                    qoq_growth = ((current_value - prev_value) / prev_value) * 100
                    new_item['qoq_growth'] = round(qoq_growth, 1)
                else:
                    new_item['qoq_growth'] = None
            else:
                new_item['qoq_growth'] = None

            # YoY growth (4 quarters ago)
            if i >= 4:
                prev_year_value = data[i - 4]['value']
                current_value = item['value']
                if prev_year_value and prev_year_value != 0:
                    yoy_growth = ((current_value - prev_year_value) / prev_year_value) * 100
                    new_item['yoy_growth'] = round(yoy_growth, 1)
                else:
                    new_item['yoy_growth'] = None
            else:
                new_item['yoy_growth'] = None

            result.append(new_item)

        return result

    def get_capital_investment_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get capital investment data with caching

        Args:
            force_refresh: Force refresh from source

        Returns:
            Capital investment data dictionary
        """
        # Redis cache check
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                data = cached_data.get("data", [])
                return {
                    "data": data,
                    "latest": data[-1] if data else None,
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated"),
                    "description": "設備投資(当期末新設固定資産合計) - 全産業（除く金融保険業）"
                }

        # Fetch from e-Stat
        raw_data = self._fetch_from_estat()
        if raw_data:
            parsed_data = self._parse_estat_data(raw_data)
            if parsed_data:
                data_with_growth = self._calculate_growth_rates(parsed_data)

                cache_payload = {
                    "data": data_with_growth,
                    "last_updated": datetime.now(JST).isoformat()
                }
                redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                self._save_file_cache(cache_payload)

                return {
                    "data": data_with_growth,
                    "latest": data_with_growth[-1] if data_with_growth else None,
                    "cached": False,
                    "source": "e-Stat",
                    "last_updated": datetime.now(JST).isoformat(),
                    "description": "設備投資(当期末新設固定資産合計) - 全産業（除く金融保険業）"
                }

        # File cache fallback
        file_cache = self._load_file_cache()
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
                "description": "設備投資(当期末新設固定資産合計) - 全産業（除く金融保険業）"
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def get_yoy_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get capital investment YoY data

        Args:
            force_refresh: Force refresh from source

        Returns:
            YoY data dictionary
        """
        result = self.get_capital_investment_data(force_refresh=force_refresh)

        if result.get("error"):
            return result

        data = result.get("data", [])
        yoy_data = [
            {"date": item["date"], "value": item["yoy_growth"]}
            for item in data
            if item.get("yoy_growth") is not None
        ]

        return {
            "data": yoy_data,
            "latest": yoy_data[-1] if yoy_data else None,
            "cached": result.get("cached", False),
            "source": result.get("source", "unknown"),
            "last_updated": result.get("last_updated")
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
            "indicator": "Capital Investment",
            "source": "e-Stat (Ministry of Finance)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# Singleton instance
capital_investment_service = CapitalInvestmentService()
