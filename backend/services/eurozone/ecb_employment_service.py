"""
ユーロ圏雇用者数変化サービス
ECB Data APIから雇用者数データを取得し、QoQ/YoYを計算

指標:
- Employment Change QoQ (前期比)
- Employment Change YoY (前年比)

データソース:
- ECB Data API (MNA dataflow)
- Series Key: Q.Y.I9.W2.S1.S1._Z.EMP._Z._T._Z.PS._Z.N

発表スケジュール:
- 2月・5月・8月・11月: 10日〜18日
- 3月・6月・9月・12月: 5日〜9日
- 発表時刻: 18:00-18:10 CET

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
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "eurozone" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_employment_cache.json"


class ECBEmploymentService:
    """ユーロ圏雇用者数変化サービス（ECB Data API）"""

    # ECB Data API
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "MNA"
    # Q = Quarterly, Y = Euro Area, I9 = Euro Area 19
    # EMP = Employment, PS = Number of persons, N = Seasonally adjusted
    SERIES_KEY = "Q.Y.I9.W2.S1.S1._Z.EMP._Z._T._Z.PS._Z.N"

    DATA_CACHE_KEY = "eurozone:employment:data"
    ECONALPHA_ID = "ecb_employment"

    def __init__(self):
        pass

    def get_ecb_employment_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """雇用者数変化データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "employment_qoq": cached_data.get("employment_qoq", []),
                        "employment_yoy": cached_data.get("employment_yoy", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ECB APIから取得
        api_result = self._fetch_from_ecb_api()
        if api_result:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "employment_qoq": api_result.get("qoq_change", []),
                "employment_yoy": api_result.get("yoy_change", []),
                "metadata": {
                    "source": "European Central Bank (ECB)",
                    "dataset": "MNA",
                    "series": self.SERIES_KEY,
                    "indicator": "Employment - Euro Area",
                    "unit": "Percent change",
                    "frequency": "Quarterly",
                    "description": "雇用者数変化（ユーロ圏）",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "employment_qoq": api_result.get("qoq_change", []),
                "employment_yoy": api_result.get("yoy_change", []),
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
                "employment_qoq": file_cache.get("employment_qoq", []),
                "employment_yoy": file_cache.get("employment_yoy", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "employment_qoq": [],
            "employment_yoy": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_ecb_api(self) -> Optional[Dict[str, List[Dict]]]:
        """ECB Data APIから雇用者数データを取得"""
        url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/{self.SERIES_KEY}"
        params = {
            "startPeriod": "2015-Q1",
            "format": "jsondata"
        }

        try:
            print(f"[ECBEmployment] Fetching from ECB API: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract time series data
            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print("[ECBEmployment] No data sets found")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print("[ECBEmployment] No series found in dataset")
                return None

            # Get the first series
            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            # Get time periods
            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print("[ECBEmployment] No time dimension found")
                return None

            time_values = time_dimension.get("values", [])

            # Build employment data list
            employment = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    date_str = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None:
                        employment.append({
                            "date": date_str,
                            "value": float(value)
                        })

            # Sort by date
            employment.sort(key=lambda x: x["date"])

            # Calculate QoQ and YoY changes
            qoq_change = self._calculate_qoq_change(employment)
            yoy_change = self._calculate_yoy_change(employment)

            print(f"[ECBEmployment] Fetched {len(employment)} employment points, {len(qoq_change)} QoQ, {len(yoy_change)} YoY")

            return {
                "employment": employment,
                "qoq_change": qoq_change,
                "yoy_change": yoy_change,
            }

        except requests.exceptions.RequestException as e:
            print(f"[ECBEmployment] API request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECBEmployment] Data parsing error: {e}")
            return None

    def _calculate_qoq_change(self, data: List[Dict]) -> List[Dict]:
        """前期比（QoQ）を計算"""
        if not data or len(data) < 2:
            return []

        result = []
        for i in range(1, len(data)):
            current = data[i]
            previous = data[i - 1]

            if current['value'] is not None and previous['value'] is not None and previous['value'] != 0:
                qoq_change = ((current['value'] - previous['value']) / previous['value']) * 100
                result.append({
                    'date': current['date'],
                    'value': round(qoq_change, 2)
                })

        return result

    def _calculate_yoy_change(self, data: List[Dict]) -> List[Dict]:
        """前年比（YoY）を計算"""
        if not data or len(data) < 5:  # Need at least 5 quarters
            return []

        result = []
        for i in range(4, len(data)):
            current = data[i]
            previous_year = data[i - 4]

            if current['value'] is not None and previous_year['value'] is not None and previous_year['value'] != 0:
                yoy_change = ((current['value'] - previous_year['value']) / previous_year['value']) * 100
                result.append({
                    'date': current['date'],
                    'value': round(yoy_change, 2)
                })

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ECBEmployment] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBEmployment] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB Employment Change",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "qoq_count": len(cached_data.get("employment_qoq", [])) if cached_data else 0,
            "yoy_count": len(cached_data.get("employment_yoy", [])) if cached_data else 0,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_employment_service = ECBEmploymentService()
