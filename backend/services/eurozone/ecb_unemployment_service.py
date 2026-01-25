"""
ユーロ圏失業率サービス
ECB Data APIからユーロ圏失業率データを取得

指標:
- Unemployment Rate (季節調整済み, 15-74歳)
- LFSI.M.I9.S.UNEHRT.TOTAL0.15_74.T

データソース:
- European Central Bank (ECB) - Labour Force Survey

発表スケジュール:
- 毎月28日〜翌月9日 18:00-18:10 CET

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_unemployment_cache.json"


class ECBUnemploymentService:
    """ユーロ圏失業率サービス (ECB Data API)"""

    DATA_CACHE_KEY = "eurozone:unemployment:data"
    ECONALPHA_ID = "ecb_unemployment"
    FMP_EVENT_PATTERN = "Unemployment Rate"

    # ECB Data API設定
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"

    # Data flow for Labour Force Survey Indicators
    DATAFLOW = "LFSI"

    # Series key
    # Key structure: DATAFLOW/Frequency.Area.Adjustment.Indicator.Population.Age.Unit
    # M = Monthly, I9 = Euro Area (changing composition)
    # S = Seasonally adjusted
    # UNEHRT = Unemployment rate
    # TOTAL0 = Total (all persons)
    # 15_74 = Age 15-74
    # T = Thousands of persons
    SERIES_KEY = "M.I9.S.UNEHRT.TOTAL0.15_74.T"

    def __init__(self):
        pass

    def get_ecb_unemployment_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """失業率データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "unemployment_rate": cached_data.get("unemployment_rate", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ECB APIから取得
        api_result = self._fetch_from_ecb()
        if api_result:
            next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN)

            cache_payload = {
                "unemployment_rate": api_result,
                "metadata": {
                    "source": "European Central Bank",
                    "dataset": self.DATAFLOW,
                    "series": self.SERIES_KEY,
                    "indicator": "Unemployment Rate - Euro Area",
                    "unit": "Percent",
                    "adjustment": "Seasonally adjusted",
                    "age_group": "15-74",
                    "description": "失業率（ユーロ圏、季節調整済み）",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "unemployment_rate": api_result,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "unemployment_rate": file_cache.get("unemployment_rate", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "unemployment_rate": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_ecb(self, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """ECB APIからデータを取得"""
        url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/{self.SERIES_KEY}"

        params = {
            "startPeriod": start_date,
            "format": "jsondata"
        }

        try:
            print(f"[ECBUnemployment] Fetching data from ECB: {self.SERIES_KEY}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # データセット抽出
            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print("[ECBUnemployment] No data sets found")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print("[ECBUnemployment] No series found in dataset")
                return None

            # 最初のシリーズを取得
            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            # 時間次元を取得
            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print("[ECBUnemployment] No time dimension found")
                return None

            time_values = time_dimension.get("values", [])

            # 結果リストを構築
            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    date_str = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if date_str and value is not None:
                        result.append({
                            "date": date_str,
                            "value": round(float(value), 2)
                        })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[ECBUnemployment] Fetched {len(result)} data points")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECBUnemployment] Request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECBUnemployment] Parse error: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ECBUnemployment] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBUnemployment] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB Unemployment Rate",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("unemployment_rate", [])) if cached_data else 0,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_unemployment_service = ECBUnemploymentService()
