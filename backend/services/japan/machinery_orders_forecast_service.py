"""
機械受注見通しサービス（日本）
e-Stat APIから機械受注見通し（予測）データを取得

指標:
- 機械受注見通し調査（四半期）
- 達成率、実績額、見通し額を提供

データソース:
- e-Stat API（内閣府経済社会総合研究所）
- 機械受注見通し調査 (Machinery Orders Forecast Survey)

発表スケジュール:
- 四半期毎

キャッシュ方式: ファイルキャッシュ
"""
import json
import logging
import os
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

try:
    from backend.core.redis_client import redis_client
except ImportError:
    from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "machinery_orders_forecast_cache.json"


class MachineryOrdersForecastService:
    """機械受注見通しサービス（e-Stat API）"""

    # e-Stat API設定
    # 機械受注見通し調査 (Machinery Orders Forecast Survey)
    # This is the quarterly forecast/outlook survey, NOT the monthly actual data (which is 0003355222)
    # Contains 達成率 (achievement rate), 実績額 (actual amount), 見通し額 (forecast amount) by tab codes
    STATS_DATA_ID = "0003355266"

    # Category codes for filtering "民間需要（船舶・電力を除く）"
    TARGET_CAT01 = '160'

    DATA_CACHE_KEY = "japan:machinery_orders_forecast:data"

    def __init__(self):
        self.api_key = os.getenv('ESTAT_API_KEY')
        if not self.api_key:
            logger.warning("ESTAT_API_KEY environment variable not set")

    def get_forecast_data(self, force_refresh: bool = False) -> List[Dict]:
        """
        機械受注見通しデータを取得

        Returns:
            List of dictionaries containing forecast data
        """
        if not force_refresh:
            # Redisキャッシュチェック
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                logger.info("Returning cached machinery orders forecast data from Redis")
                return cached_data

            # ファイルキャッシュチェック
            file_cache = self._load_file_cache()
            if file_cache:
                logger.info("Returning cached machinery orders forecast data from file")
                # Redisにも保存
                redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                return file_cache

        # e-Stat APIからデータ取得
        logger.info("Fetching fresh machinery orders forecast data from e-Stat API")
        try:
            raw_data = self._fetch_from_estat()
            parsed_data = self._parse_forecast_data(raw_data)

            # キャッシュ保存
            redis_client.set(self.DATA_CACHE_KEY, parsed_data, expire=0)
            self._save_file_cache(parsed_data)

            return parsed_data

        except Exception as e:
            logger.error(f"Error fetching machinery orders forecast data: {e}")

            # エラー時はファイルキャッシュにフォールバック
            file_cache = self._load_file_cache()
            if file_cache:
                return file_cache

            return []

    def _fetch_from_estat(self) -> Dict:
        """e-Stat APIからデータ取得"""
        if not self.api_key:
            raise ValueError("ESTAT_API_KEY environment variable not set")

        url = "http://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

        params = {
            'appId': self.api_key,
            'lang': 'J',
            'statsDataId': self.STATS_DATA_ID,
            'metaGetFlg': 'Y',
            'cntGetFlg': 'N',
        }

        logger.info(f"Fetching machinery orders forecast data from e-Stat API (statsDataId: {self.STATS_DATA_ID})")
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        if 'GET_STATS_DATA' not in data:
            raise ValueError(f"Unexpected response structure: {data}")

        result = data['GET_STATS_DATA'].get('RESULT', {})
        if result.get('STATUS') != 0:
            error_msg = result.get('ERROR_MSG', 'Unknown error')
            raise ValueError(f"e-Stat API error: {error_msg}")

        logger.info("Successfully fetched machinery orders forecast data from e-Stat")
        return data

    def _parse_forecast_data(self, raw_data: Dict) -> List[Dict]:
        """
        e-Statの生データをパース
        """
        values = raw_data['GET_STATS_DATA']['STATISTICAL_DATA']['DATA_INF']['VALUE']

        if not isinstance(values, list):
            values = [values]

        # Group data by time period and tab
        # Structure: {date: {tab: {cat02: value}}}
        data_by_period_and_tab = {}

        for item in values:
            cat01 = item.get('@cat01', '')
            cat02 = item.get('@cat02', '')
            tab = item.get('@tab', '')
            time_code = item.get('@time', '')
            value_str = item.get('$', '')

            # Filter for target category
            if cat01 != self.TARGET_CAT01:
                continue

            if not time_code or not value_str:
                continue

            # Parse time code (format: YYYY00MMSS where MM is start month, SS is end month)
            # Examples: 2025000103 = 2025 Q1 (Jan-Mar), 2025000406 = 2025 Q2 (Apr-Jun)
            try:
                if len(time_code) == 10:
                    year = int(time_code[:4])
                    start_month = int(time_code[6:8])
                    end_month = int(time_code[8:10])

                    # Determine quarter from start-end month combination
                    if start_month == 1 and end_month == 3:
                        month = 3  # Q1
                    elif start_month == 4 and end_month == 6:
                        month = 6  # Q2
                    elif start_month == 7 and end_month == 9:
                        month = 9  # Q3
                    elif start_month == 10 and end_month == 12:
                        month = 12  # Q4
                    else:
                        logger.warning(f"Skipping unrecognized quarter: start_month={start_month}, end_month={end_month}, time_code={time_code}")
                        continue

                    date_str = f"{year}-{month:02d}-01"
                    value = float(value_str)

                    if date_str not in data_by_period_and_tab:
                        data_by_period_and_tab[date_str] = {}
                    if tab not in data_by_period_and_tab[date_str]:
                        data_by_period_and_tab[date_str][tab] = {}

                    # Store value with cat02 key to handle multiple cat02 values
                    data_by_period_and_tab[date_str][tab][cat02] = value

            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse time code {time_code}: {e}")
                continue

        # Select best value for each period/tab combination
        # cat02コードの選択ルール:
        # - 達成率 (tab='110'): 季節調整値 (cat02='100') を優先
        # - 実績額 (tab='120'): 原系列 (cat02='110') を使用（前期比計算のため）
        # - 見通し額 (tab='130'): 原系列 (cat02='110') を使用（PDFの計算式と一致させるため）
        #
        # 注意: e-Stat APIの季節調整見通し額はPDFの値と異なるため、
        # 原系列を使用して前期比を計算することでPDFと一致する結果を得る

        data_by_period = {}
        for date_str, tabs_data in data_by_period_and_tab.items():
            data_by_period[date_str] = {}

            for tab, cat02_values in tabs_data.items():
                selected_value = None

                if tab == '110':  # 達成率 [%]
                    # 達成率は季節調整値を優先
                    if '100' in cat02_values:
                        selected_value = cat02_values['100']
                    elif '110' in cat02_values:
                        selected_value = cat02_values['110']
                    data_by_period[date_str]['achievement_rate'] = selected_value

                elif tab == '120':  # 実績額 [100万円]
                    # 実績額は原系列を使用（前期比計算のため）
                    if '110' in cat02_values:
                        selected_value = cat02_values['110']
                    elif '100' in cat02_values:
                        selected_value = cat02_values['100']
                    data_by_period[date_str]['actual_amount'] = selected_value

                elif tab == '130':  # 見通し額 [100万円]
                    # 見通し額は原系列を使用（PDFと一致させるため）
                    if '110' in cat02_values:
                        selected_value = cat02_values['110']
                    elif '100' in cat02_values:
                        selected_value = cat02_values['100']
                    data_by_period[date_str]['forecast_amount'] = selected_value

        # Build final data structure with QoQ calculation
        parsed_data = []
        sorted_dates = sorted(data_by_period.keys())

        # まず時系列順（古い→新しい）でデータを作成
        temp_data = []
        for date_str in sorted_dates:
            period_data = data_by_period[date_str]

            achievement_rate = period_data.get('achievement_rate')
            actual_amount = period_data.get('actual_amount')
            forecast_amount = period_data.get('forecast_amount')

            # For periods without actual data, set achievement_rate to None
            if achievement_rate is None or actual_amount is None:
                achievement_rate = None

            temp_data.append({
                'date': date_str,
                'achievement_rate': achievement_rate,
                'actual_amount': actual_amount,
                'forecast_amount': forecast_amount,
                'unit': '百万円'
            })

        # 前期比を計算
        # 見通しの前期比 = (当期見通し額 / 前期実績額 - 1) * 100
        logger.info(f"Calculating QoQ for {len(temp_data)} periods")
        for i, item in enumerate(temp_data):
            if i > 0 and item.get('forecast_amount') is not None:
                prev_actual = temp_data[i - 1].get('actual_amount')
                logger.debug(f"Period {item['date']}: forecast={item.get('forecast_amount')}, prev_actual={prev_actual}")
                if prev_actual is not None and prev_actual > 0:
                    qoq_change = ((item['forecast_amount'] / prev_actual) - 1) * 100
                    item['qoq_change'] = round(qoq_change, 1)
                    logger.debug(f"  -> QoQ = {item['qoq_change']}%")
                else:
                    item['qoq_change'] = None
                    logger.debug(f"  -> QoQ = None (prev_actual missing or zero)")
            else:
                item['qoq_change'] = None

        # Sort by date descending for table display
        parsed_data = sorted(temp_data, key=lambda x: x['date'], reverse=True)

        logger.info(f"Successfully parsed {len(parsed_data)} forecast data points")
        return parsed_data

    def refresh_data(self) -> Dict:
        """
        Force refresh data from e-Stat and update cache

        Returns:
            Dictionary with refresh status and data count
        """
        try:
            logger.info("Manually refreshing machinery orders forecast data")
            data = self.get_forecast_data(force_refresh=True)

            return {
                "status": "success",
                "message": "Successfully refreshed machinery orders forecast data",
                "data_points": len(data),
                "last_updated": datetime.now(JST).isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to refresh machinery orders forecast data: {e}")
            return {
                "status": "error",
                "message": str(e),
                "data_points": 0
            }

    def _load_file_cache(self) -> Optional[List[Dict]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: List[Dict]) -> None:
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
            "indicator": "Machinery Orders Forecast (Japan)",
            "source": "e-Stat API (Cabinet Office)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "data_count": len(cached_data) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
machinery_orders_forecast_service = MachineryOrdersForecastService()
