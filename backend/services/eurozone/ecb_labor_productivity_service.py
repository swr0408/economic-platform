"""
ユーロ圏労働生産性サービス
ECB Data APIから労働生産性データを取得

指標:
- Labor Productivity per Hour Worked (時間あたり労働生産性)
- Labor Productivity per Person (就業者あたり労働生産性)
- 前年比 (YoY) 変化率

データソース:
- ECB Data API (MNA dataflow)
- Series Keys:
  - per_hour: Q.Y.I10.W0.S1.S1._Z.LPR_HW._Z._T._Z.IX.LR.N
  - per_person: Q.Y.I10.W0.S1.S1._Z.LPR_PS._Z._T._Z.IX.LR.N

発表スケジュール:
- 2月・5月・8月・11月: 10日〜18日
- 3月・6月・9月・12月: 5日〜9日
- 発表時刻: 18:00-18:10 CET
- ※雇用者数変化と同時発表

キャッシュ方式: FMP発表日時ベース判定方式（ecb_employment IDを使用）
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_labor_productivity_cache.json"


class ECBLaborProductivityService:
    """ユーロ圏労働生産性サービス（ECB Data API）"""

    # ECB Data API
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "MNA"

    # Series keys
    # Q = Quarterly, Y = Euro Area, I9 = Euro Area 19
    # W0 = Not seasonally adjusted (raw)
    # LPR_HW = Labor productivity per hour worked
    # LPR_PS = Labor productivity per person
    # IX = Index, LR = Chain linked volumes, N = Seasonally adjusted
    SERIES_KEYS = {
        "per_hour": "Q.Y.I10.W0.S1.S1._Z.LPR_HW._Z._T._Z.IX.LR.N",
        "per_person": "Q.Y.I10.W0.S1.S1._Z.LPR_PS._Z._T._Z.IX.LR.N",
    }

    DATA_CACHE_KEY = "eurozone:labor_productivity:data"
    # 雇用者数変化と同時発表のため、同じECONALPHA_IDを使用
    ECONALPHA_ID = "ecb_employment"

    def __init__(self):
        pass

    def get_ecb_labor_productivity_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """労働生産性データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "per_hour": cached_data.get("per_hour", []),
                        "per_person": cached_data.get("per_person", []),
                        "per_hour_yoy": cached_data.get("per_hour_yoy", []),
                        "per_person_yoy": cached_data.get("per_person_yoy", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ECB APIから取得
        per_hour = self._fetch_series_data(self.SERIES_KEYS["per_hour"]) or []
        per_person = self._fetch_series_data(self.SERIES_KEYS["per_person"]) or []

        # 前年比を計算
        per_hour_yoy = self._calculate_yoy_change(per_hour)
        per_person_yoy = self._calculate_yoy_change(per_person)

        has_data = len(per_hour) > 0 or len(per_person) > 0

        if has_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("per_hour", "per_person", "per_hour_yoy", "per_person_yoy"),
                _max_date_of(per_hour, per_person, per_hour_yoy, per_person_yoy), now_str
            )
            cache_payload = {
                "per_hour": per_hour,
                "per_person": per_person,
                "per_hour_yoy": per_hour_yoy,
                "per_person_yoy": per_person_yoy,
                "metadata": {
                    "source": "European Central Bank (ECB)",
                    "dataset": "MNA",
                    "indicator": "Labor Productivity - Euro Area",
                    "unit_index": "Index (chain linked volumes)",
                    "unit_yoy": "Percent change (YoY)",
                    "frequency": "Quarterly",
                    "description": "労働生産性（ユーロ圏）",
                },
                "next_release": next_release,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "per_hour": per_hour,
                "per_person": per_person,
                "per_hour_yoy": per_hour_yoy,
                "per_person_yoy": per_person_yoy,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "per_hour": file_cache.get("per_hour", []),
                "per_person": file_cache.get("per_person", []),
                "per_hour_yoy": file_cache.get("per_hour_yoy", []),
                "per_person_yoy": file_cache.get("per_person_yoy", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "per_hour": [],
            "per_person": [],
            "per_hour_yoy": [],
            "per_person_yoy": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_series_data(self, series_key: str, start_date: str = "2015-Q1") -> Optional[List[Dict]]:
        """ECB Data APIから単一シリーズデータを取得"""
        url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/{series_key}"
        params = {
            "startPeriod": start_date,
            "format": "jsondata"
        }

        try:
            print(f"[ECBLaborProductivity] Fetching from ECB API: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract time series data
            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECBLaborProductivity] No data sets found for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECBLaborProductivity] No series found for {series_key}")
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
                print(f"[ECBLaborProductivity] No time dimension found for {series_key}")
                return None

            time_values = time_dimension.get("values", [])

            # Build result list
            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    date_str = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None:
                        result.append({
                            "date": date_str,
                            "value": float(value)
                        })

            # Sort by date
            result.sort(key=lambda x: x["date"])

            print(f"[ECBLaborProductivity] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECBLaborProductivity] API request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECBLaborProductivity] Data parsing error for {series_key}: {e}")
            return None

    def _calculate_yoy_change(self, data: List[Dict]) -> List[Dict]:
        """前年比（YoY）を計算（4四半期前との比較）"""
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
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ECBLaborProductivity] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBLaborProductivity] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB Labor Productivity",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "per_hour_count": len(cached_data.get("per_hour", [])) if cached_data else 0,
            "per_person_count": len(cached_data.get("per_person", [])) if cached_data else 0,
            "per_hour_yoy_count": len(cached_data.get("per_hour_yoy", [])) if cached_data else 0,
            "per_person_yoy_count": len(cached_data.get("per_person_yoy", [])) if cached_data else 0,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_labor_productivity_service = ECBLaborProductivityService()
