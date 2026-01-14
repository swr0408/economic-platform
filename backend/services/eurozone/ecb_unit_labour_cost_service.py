"""
ユーロ圏労働コスト指数サービス
ECB Data APIからLabour Cost Index (LCI)データを取得

指標:
- Labour Cost Index (労働コスト指数)
- 前年比 (YoY) 変化率
- 前期比 (QoQ) 変化率

データソース:
- ECB Data API (LCI dataflow)
- Series Key: Q.I9.W.LCI_TOT.B-S_X_O
  - Q = Quarterly
  - I9 = Euro Area 20 (fixed composition) as of 1 January 2023
  - W = Calendar adjusted data
  - LCI_TOT = Labour cost index - total labour costs
  - B-S_X_O = Total economy (industry, construction and services)

発表スケジュール:
- 3月・6月・9月・12月の13日〜21日（四半期ごと）
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_labour_cost_index_cache.json"


class ECBUnitLabourCostService:
    """ユーロ圏労働コスト指数サービス（ECB Data API - LCI）"""

    # ECB Data API
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "LCI"

    # Series key for Labour Cost Index
    # Q = Quarterly
    # I9 = Euro Area 20 (fixed composition)
    # Y = Calendar and seasonally adjusted data
    # LCI_T = Total labour costs
    # BTS = Industry, construction and services (total economy)
    SERIES_KEY = "Q.I9.Y.LCI_T.BTS"

    DATA_CACHE_KEY = "eurozone:labour_cost_index:data"
    ECONALPHA_ID = "ecb_unit_labour_cost"

    def __init__(self):
        pass

    def get_ecb_unit_labour_cost_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """労働コスト指数データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "unit_labour_cost": cached_data.get("unit_labour_cost", []),
                        "unit_labour_cost_yoy": cached_data.get("unit_labour_cost_yoy", []),
                        "unit_labour_cost_qoq": cached_data.get("unit_labour_cost_qoq", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ECB APIから取得
        lci_data = self._fetch_series_data(self.SERIES_KEY) or []

        has_data = len(lci_data) > 0

        if has_data:
            # 前年比・前期比を計算
            lci_yoy = self._calculate_yoy_change(lci_data)
            lci_qoq = self._calculate_qoq_change(lci_data)

            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "unit_labour_cost": lci_data,
                "unit_labour_cost_yoy": lci_yoy,
                "unit_labour_cost_qoq": lci_qoq,
                "metadata": {
                    "source": "European Central Bank (ECB) / Eurostat",
                    "dataset": "LCI",
                    "indicator": "Labour Cost Index - Euro Area 20",
                    "unit_index": "Index (2020=100)",
                    "unit_yoy": "Percent change (YoY)",
                    "unit_qoq": "Percent change (QoQ)",
                    "frequency": "Quarterly",
                    "description": "労働コスト指数（ユーロ圏）- 時間あたり労働コスト",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "unit_labour_cost": lci_data,
                "unit_labour_cost_yoy": lci_yoy,
                "unit_labour_cost_qoq": lci_qoq,
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
                "unit_labour_cost": file_cache.get("unit_labour_cost", []),
                "unit_labour_cost_yoy": file_cache.get("unit_labour_cost_yoy", []),
                "unit_labour_cost_qoq": file_cache.get("unit_labour_cost_qoq", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "unit_labour_cost": [],
            "unit_labour_cost_yoy": [],
            "unit_labour_cost_qoq": [],
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
            print(f"[ECBLabourCostIndex] Fetching from ECB API: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract time series data
            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECBLabourCostIndex] No data sets found for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECBLabourCostIndex] No series found for {series_key}")
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
                print(f"[ECBLabourCostIndex] No time dimension found for {series_key}")
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

            print(f"[ECBLabourCostIndex] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECBLabourCostIndex] API request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECBLabourCostIndex] Data parsing error for {series_key}: {e}")
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

    def _calculate_qoq_change(self, data: List[Dict]) -> List[Dict]:
        """前期比（QoQ）を計算（1四半期前との比較）"""
        if not data or len(data) < 2:
            return []

        result = []
        for i in range(1, len(data)):
            current = data[i]
            previous_quarter = data[i - 1]

            if current['value'] is not None and previous_quarter['value'] is not None and previous_quarter['value'] != 0:
                qoq_change = ((current['value'] - previous_quarter['value']) / previous_quarter['value']) * 100
                result.append({
                    'date': current['date'],
                    'value': round(qoq_change, 2)
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
            print(f"[ECBLabourCostIndex] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBLabourCostIndex] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB Labour Cost Index",
            "source": "ECB Data API (LCI)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "unit_labour_cost_count": len(cached_data.get("unit_labour_cost", [])) if cached_data else 0,
            "unit_labour_cost_yoy_count": len(cached_data.get("unit_labour_cost_yoy", [])) if cached_data else 0,
            "unit_labour_cost_qoq_count": len(cached_data.get("unit_labour_cost_qoq", [])) if cached_data else 0,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_unit_labour_cost_service = ECBUnitLabourCostService()
