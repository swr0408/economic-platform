"""
四半期GDP成長率サービス
e-Stat APIから日本の四半期GDP成長率データを取得

指標:
- GDP成長率（前期比）: 0003113542 TAB_CODE=14
- GDP成長率（前年同期比）: 0003113542 TAB_CODE=13

データソース:
- e-Stat API（内閣府）

発表スケジュール:
- 四半期毎（速報・改定値）
- FMPカレンダーで更新判定

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import logging
import os
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.usa.fred_utils import load_file_cache, save_file_cache

logger = logging.getLogger(__name__)

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
QOQ_CACHE_FILE = CACHE_DIR / "quarterly_gdp_qoq.json"
YOY_CACHE_FILE = CACHE_DIR / "quarterly_gdp_yoy.json"

# Redisキー
QOQ_REDIS_KEY = "japan:gdp:qoq"
YOY_REDIS_KEY = "japan:gdp:yoy"


class QuarterlyGDPService:
    """四半期GDP成長率サービス（e-Stat API）"""

    # e-Stat API設定
    ESTAT_API_URL = "http://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    STATS_DATA_ID_QOQ = "0003113542"  # 国内総生産（実質季節調整系列・成長率）
    STATS_DATA_ID_AMOUNT = "0003109750"  # 国内総生産（実質季節調整系列・金額）

    # フィルターコード
    TAB_CODE_ZENKI = "14"  # 前期比 (Quarter-on-Quarter)
    TAB_CODE_YOY = "13"  # 前年同期比 (Year-on-Year)
    TAB_CODE_KINGAKU = "11"  # 金額 (Amount) - 使用しない
    CAT01_CODE_GDP = "11"  # 国内総生産(支出側)

    # FMPイベント名（更新判定用）
    FMP_EVENT_PATTERN = "GDP Growth Rate QoQ"

    def __init__(self):
        """Initialize Quarterly GDP service"""
        self.api_key = os.getenv('ESTAT_API_KEY')

        if not self.api_key:
            logger.warning("ESTAT_API_KEY not found in environment variables")

    def _fetch_from_estat_api(self, stats_data_id: str, tab_code: str) -> Optional[Dict]:
        """
        Fetch data from e-Stat API

        Args:
            stats_data_id: Statistics data ID
            tab_code: Tab code for filtering

        Returns:
            Raw API response data
        """
        try:
            if not self.api_key:
                logger.error("e-Stat API key not configured")
                return None

            logger.info(f"Fetching data from e-Stat API (statsDataId: {stats_data_id})")

            params = {
                "appId": self.api_key,
                "lang": "J",
                "statsDataId": stats_data_id,
                "metaGetFlg": "Y",
                "cntGetFlg": "N",
                "explanationGetFlg": "Y",
                "annotationGetFlg": "Y",
                "sectionHeaderFlg": "1",
                "replaceSpChars": "0",
                "cdTab": tab_code,
                "cdCat01": self.CAT01_CODE_GDP,
            }

            response = requests.get(self.ESTAT_API_URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Successfully fetched data from e-Stat API")

            return data

        except requests.RequestException as e:
            logger.error(f"Error fetching data from e-Stat API: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in e-Stat API fetch: {e}")
            return None

    def _parse_time_code(self, time_code: str) -> Optional[tuple[int, str]]:
        """
        Parse e-Stat time code to year and quarter

        Args:
            time_code: Time code like "1994000406"

        Returns:
            Tuple of (year, quarter_str) or None
        """
        try:
            year = int(time_code[:4])
            month_range = time_code[4:]

            # Map month range to quarter
            quarter_map = {
                "000103": "Q1",  # 1-3月
                "000406": "Q2",  # 4-6月
                "000709": "Q3",  # 7-9月
                "001012": "Q4",  # 10-12月
            }

            quarter = quarter_map.get(month_range)
            if not quarter:
                return None

            return year, quarter

        except Exception:
            return None

    def _parse_qoq_response(self, api_data: Dict) -> List[Dict[str, Any]]:
        """
        Parse e-Stat API response for QoQ data

        Args:
            api_data: Raw API response

        Returns:
            List of data points
        """
        try:
            if 'GET_STATS_DATA' not in api_data:
                logger.error("Invalid API response structure")
                return []

            stats_data = api_data['GET_STATS_DATA']

            if 'STATISTICAL_DATA' not in stats_data:
                logger.error("No statistical data in response")
                return []

            stat_data = stats_data['STATISTICAL_DATA']

            if 'DATA_INF' not in stat_data or 'VALUE' not in stat_data['DATA_INF']:
                logger.error("No data values in response")
                return []

            values = stat_data['DATA_INF']['VALUE']
            if not isinstance(values, list):
                values = [values]

            logger.info(f"Found {len(values)} raw data points")

            # Process values
            series_data = []
            for val in values:
                try:
                    time_code = val.get('@time', '')
                    if not time_code:
                        continue

                    parsed = self._parse_time_code(time_code)
                    if not parsed:
                        continue

                    year, quarter = parsed

                    # Get value
                    value_str = val.get('$', '')
                    if not value_str or value_str == '-':
                        continue

                    # Remove % sign and convert to float
                    value_str = value_str.replace('%', '').strip()
                    try:
                        value = float(value_str)
                    except ValueError:
                        continue

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

            # Filter to data from 2000 onwards
            if series_data:
                series_data = [p for p in series_data if p["date"] >= "2000-Q1"]

            logger.info(f"Processed {len(series_data)} QoQ GDP data points")
            return series_data

        except Exception as e:
            logger.error(f"Error parsing e-Stat response: {e}", exc_info=True)
            return []

    def _calculate_yoy_from_amount(self, api_data: Dict) -> List[Dict[str, Any]]:
        """
        Calculate Year-over-Year growth rate from amount data

        Formula: YoY = ((current - prev_year) / prev_year) * 100

        Args:
            api_data: Raw API response with amount values

        Returns:
            List of YoY data points
        """
        try:
            if 'GET_STATS_DATA' not in api_data:
                return []

            stats_data = api_data['GET_STATS_DATA']

            if 'STATISTICAL_DATA' not in stats_data:
                return []

            stat_data = stats_data['STATISTICAL_DATA']

            if 'DATA_INF' not in stat_data or 'VALUE' not in stat_data['DATA_INF']:
                return []

            values = stat_data['DATA_INF']['VALUE']
            if not isinstance(values, list):
                values = [values]

            # Parse amount data
            amount_data = []
            for val in values:
                try:
                    time_code = val.get('@time', '')
                    if not time_code:
                        continue

                    parsed = self._parse_time_code(time_code)
                    if not parsed:
                        continue

                    year, quarter = parsed

                    value_str = val.get('$', '')
                    if not value_str or value_str == '-':
                        continue

                    try:
                        amount = float(value_str)
                    except ValueError:
                        continue

                    date_str = f"{year}-{quarter}"

                    amount_data.append({
                        "date": date_str,
                        "amount": amount
                    })

                except Exception:
                    continue

            # Sort by date
            amount_data.sort(key=lambda x: (int(x["date"][:4]), x["date"][5:]))

            # Calculate YoY (need 4 quarters of history)
            yoy_data = []
            for i in range(len(amount_data)):
                if i >= 4:
                    current = amount_data[i]
                    prev_year = amount_data[i - 4]

                    yoy_growth = ((current['amount'] - prev_year['amount']) / prev_year['amount']) * 100

                    yoy_data.append({
                        "date": current['date'],
                        "value": round(yoy_growth, 2)
                    })

            # Filter to data from 2000 onwards
            if yoy_data:
                yoy_data = [p for p in yoy_data if p["date"] >= "2000-Q1"]

            logger.info(f"Calculated {len(yoy_data)} YoY GDP data points")
            return yoy_data

        except Exception as e:
            logger.error(f"Error calculating YoY from amount data: {e}", exc_info=True)
            return []

    def _get_next_release_from_fmp(self) -> Optional[str]:
        """Get next GDP release date from FMP calendar"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc
                    FROM economic_calendar_events
                    WHERE country = 'JP'
                      AND event ILIKE :pattern
                      AND datetime_utc > NOW()
                    ORDER BY datetime_utc ASC
                    LIMIT 1
                """)
                result = session.execute(query, {"pattern": f"%{self.FMP_EVENT_PATTERN}%"}).fetchone()

                if result:
                    return result[0].isoformat()

            return None

        except Exception as e:
            logger.error(f"Error getting next release from FMP: {e}")
            return None

    def _should_refresh_by_fmp(self, last_updated_str: str) -> bool:
        """
        Check if cache should be refreshed based on FMP schedule

        Args:
            last_updated_str: Last update timestamp

        Returns:
            True if refresh needed
        """
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            with SessionLocal() as session:
                # Check if there's a release between last_updated and now
                query = text("""
                    SELECT datetime_utc
                    FROM economic_calendar_events
                    WHERE country = 'JP'
                      AND event ILIKE :pattern
                      AND datetime_utc > :last_updated
                      AND datetime_utc <= :now
                    ORDER BY datetime_utc DESC
                    LIMIT 1
                """)
                result = session.execute(query, {
                    "pattern": f"%{self.FMP_EVENT_PATTERN}%",
                    "last_updated": last_updated,
                    "now": now
                }).fetchone()

                if result:
                    logger.info(f"GDP release detected at {result[0]}, refresh needed")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking FMP schedule: {e}")
            # Default to refresh every 7 days if FMP check fails
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                days_since = (datetime.now(JST) - last_updated).days
                return days_since >= 7
            except Exception:
                return True

    def get_quarterly_gdp_qoq(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get Quarterly GDP Growth Rate (QoQ) data

        Args:
            force_refresh: Force refresh from source

        Returns:
            GDP QoQ data dictionary
        """
        # Check cache
        if not force_refresh:
            cached_data = redis_client.get(QOQ_REDIS_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP QoQ from Redis")
                    return {**cached_data, "cached": True}

            file_cache = load_file_cache(QOQ_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP QoQ from file")
                    redis_client.set(QOQ_REDIS_KEY, file_cache, expire=0)
                    return {**file_cache, "cached": True}

        # Fetch from e-Stat API
        api_data = self._fetch_from_estat_api(self.STATS_DATA_ID_QOQ, self.TAB_CODE_ZENKI)
        if api_data:
            qoq_data = self._parse_qoq_response(api_data)

            if qoq_data:
                latest = qoq_data[-1] if qoq_data else None
                next_release = self._get_next_release_from_fmp()

                cache_payload = {
                    "data": qoq_data,
                    "latest": latest,
                    "next_release": next_release,
                    "last_updated": datetime.now(JST).isoformat(),
                    "source": "e-Stat (Cabinet Office)"
                }

                redis_client.set(QOQ_REDIS_KEY, cache_payload, expire=0)
                save_file_cache(QOQ_CACHE_FILE, cache_payload)

                return {**cache_payload, "cached": False}

        # Fallback to file cache
        file_cache = load_file_cache(QOQ_CACHE_FILE)
        if file_cache:
            return {**file_cache, "cached": True, "source": "file (fallback)"}

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": datetime.now(JST).isoformat(),
            "error": "No data available"
        }

    def get_quarterly_gdp_yoy(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get Quarterly GDP Growth Rate (YoY) data

        前年同期比データをe-Stat APIから直接取得（TAB_CODE=13）

        Args:
            force_refresh: Force refresh from source

        Returns:
            GDP YoY data dictionary
        """
        # Check cache
        if not force_refresh:
            cached_data = redis_client.get(YOY_REDIS_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP YoY from Redis")
                    return {**cached_data, "cached": True}

            file_cache = load_file_cache(YOY_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh_by_fmp(last_updated_str):
                    logger.info("Returning cached GDP YoY from file")
                    redis_client.set(YOY_REDIS_KEY, file_cache, expire=0)
                    return {**file_cache, "cached": True}

        # Fetch from e-Stat API - 季節調整済み金額データから前年同期比を計算
        # 注: 季節調整系列には直接の前年同期比データがないため、金額から計算
        api_data = self._fetch_from_estat_api(self.STATS_DATA_ID_AMOUNT, self.TAB_CODE_KINGAKU)
        if api_data:
            yoy_data = self._calculate_yoy_from_amount(api_data)

            if yoy_data:
                latest = yoy_data[-1] if yoy_data else None
                next_release = self._get_next_release_from_fmp()

                cache_payload = {
                    "data": yoy_data,
                    "latest": latest,
                    "next_release": next_release,
                    "last_updated": datetime.now(JST).isoformat(),
                    "source": "e-Stat (Cabinet Office)",
                    "calculation_method": "Calculated from seasonally adjusted GDP amount data"
                }

                redis_client.set(YOY_REDIS_KEY, cache_payload, expire=0)
                save_file_cache(YOY_CACHE_FILE, cache_payload)

                return {**cache_payload, "cached": False}

        # Fallback to file cache
        file_cache = load_file_cache(YOY_CACHE_FILE)
        if file_cache:
            return {**file_cache, "cached": True, "source": "file (fallback)"}

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": datetime.now(JST).isoformat(),
            "error": "No data available"
        }

    def invalidate_cache(self) -> bool:
        """Invalidate all GDP caches"""
        qoq_deleted = redis_client.delete(QOQ_REDIS_KEY)
        yoy_deleted = redis_client.delete(YOY_REDIS_KEY)
        return qoq_deleted or yoy_deleted

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        qoq_exists = redis_client.exists(QOQ_REDIS_KEY)
        yoy_exists = redis_client.exists(YOY_REDIS_KEY)
        qoq_data = redis_client.get(QOQ_REDIS_KEY) if qoq_exists else None
        yoy_data = redis_client.get(YOY_REDIS_KEY) if yoy_exists else None

        return {
            "indicator": "Japan Quarterly GDP",
            "source": "e-Stat (Cabinet Office)",
            "qoq": {
                "cache_key": QOQ_REDIS_KEY,
                "exists": qoq_exists,
                "last_updated": qoq_data.get("last_updated") if qoq_data else None,
                "data_count": len(qoq_data.get("data", [])) if qoq_data else 0,
                "latest": qoq_data.get("latest") if qoq_data else None,
                "file_cache_exists": QOQ_CACHE_FILE.exists()
            },
            "yoy": {
                "cache_key": YOY_REDIS_KEY,
                "exists": yoy_exists,
                "last_updated": yoy_data.get("last_updated") if yoy_data else None,
                "data_count": len(yoy_data.get("data", [])) if yoy_data else 0,
                "latest": yoy_data.get("latest") if yoy_data else None,
                "file_cache_exists": YOY_CACHE_FILE.exists()
            },
            "next_release": self._get_next_release_from_fmp()
        }


# シングルトンインスタンス
_service_instance: Optional[QuarterlyGDPService] = None


def get_quarterly_gdp_service() -> QuarterlyGDPService:
    """Get or create QuarterlyGDPService singleton instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = QuarterlyGDPService()
    return _service_instance


# グローバルサービスインスタンス
quarterly_gdp_service = get_quarterly_gdp_service()
