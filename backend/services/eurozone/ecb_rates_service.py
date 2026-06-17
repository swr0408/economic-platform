"""
ECB預金ファシリティ金利サービス
ECB Data APIから金利データを取得

指標:
- ECB Deposit Facility Rate: ECB預金ファシリティ金利

データソース:
- ECB Data API (https://data-api.ecb.europa.eu)

発表スケジュール:
- 不定期（ECB理事会開催日）
- 発表時刻: 21:15-21:25 JST（冬時間）/ 22:15-22:25 JST（夏時間）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_rates_cache.json"


class ECBRatesService:
    """ECB預金ファシリティ金利サービス"""

    # ECB Data API
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "FM"
    # D = Daily, U2 = Euro Area, EUR = Euro, 4F = Instrument, KR = Category
    # DFR = Deposit Facility Rate, LEV = Level
    RATE_KEY = "D.U2.EUR.4F.KR.DFR.LEV"

    DATA_CACHE_KEY = "monetary_policy:ecb_rates:data"
    ECONALPHA_ID = "eu_ecb_rate"

    def __init__(self):
        pass

    def get_ecb_rates_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ECB金利データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIから取得
        api_result = self._fetch_from_ecb_api()
        if api_result:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            latest = api_result[-1] if api_result else None
            cache_payload = {
                "data": api_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
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

    def _fetch_from_ecb_api(self, start_date: str = "2010-01-01") -> List[Dict[str, Any]]:
        """ECB Data APIからデータを取得"""
        try:
            url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/{self.RATE_KEY}"

            params = {
                'startPeriod': start_date,
                'format': 'jsondata',
                'detail': 'dataonly'
            }

            print(f"Fetching ECB rate data from {url}")

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Parse ECB SDMX-JSON format
            result = []

            if 'dataSets' in data and len(data['dataSets']) > 0:
                dataset = data['dataSets'][0]

                if 'series' in dataset:
                    # Get time dimension
                    dimensions = data.get('structure', {}).get('dimensions', {})
                    observation_dimension = dimensions.get('observation', [])

                    time_values = []
                    for dim in observation_dimension:
                        if dim.get('id') == 'TIME_PERIOD':
                            time_values = [v.get('id') for v in dim.get('values', [])]
                            break

                    # Extract series data
                    for series_key, series_data in dataset['series'].items():
                        observations = series_data.get('observations', {})

                        for obs_index, obs_value in observations.items():
                            if int(obs_index) < len(time_values):
                                date_str = time_values[int(obs_index)]
                                value = obs_value[0] if isinstance(obs_value, list) else obs_value

                                if value is not None:
                                    result.append({
                                        'date': date_str,
                                        'value': float(value),
                                        'deposit_facility': float(value)
                                    })

            # 日付でソート
            result.sort(key=lambda x: x['date'])

            print(f"Fetched {len(result)} ECB rate data points")
            return result

        except Exception as e:
            print(f"Error fetching from ECB API: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB Deposit Facility Rate",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_rates_service = ECBRatesService()
