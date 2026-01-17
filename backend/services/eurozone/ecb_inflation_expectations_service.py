"""
ECB Consumer Expectations Survey (CES) - インフレ期待サービス
ECBから消費者インフレ期待データを取得

指標:
- 消費者インフレ期待（12ヶ月先）: C1120
- 消費者インフレ期待（3年先）: C1220
- 消費者インフレ期待（5年先）: E2020

データソース:
- ECB Data API (CES dataflow)
- https://data.ecb.europa.eu/data/datasets/CES

発表スケジュール:
- 毎月発表（不定期）
- FMPカレンダーから次回発表日を取得

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
CET = ZoneInfo("Europe/Berlin")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_inflation_expectations_cache.json"


class ECBInflationExpectationsService:
    """ECB消費者インフレ期待サービス"""

    DATA_CACHE_KEY = "eurozone:ecb_inflation_expectations:data"

    # ECB Data API設定
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "CES"

    # シリーズキー（ECB Data API）
    # Key structure: CES.Frequency.Area.Breakdown.Category.Variable.Concept.Statistic
    # M = Monthly, Z18 = Euro area 11, ALL = All breakdown, T = Total
    SERIES_KEYS = {
        # 12ヶ月先インフレ期待 (Weighted Median)
        "inflation_12m": "M.Z18.ALL.T.C1120.NUM_VAR.WM",
        # 3年先インフレ期待 (Weighted Median)
        "inflation_3y": "M.Z18.ALL.T.C1220.NUM_VAR.WM",
        # 5年先インフレ期待 (Weighted Median)
        "inflation_5y": "M.Z18.ALL.T.E2020.NUM_VAR.WM",
    }

    # FMPイベントパターン（次回発表日取得用）
    FMP_EVENT_PATTERN = "Consumer Inflation Expectation"

    def __init__(self):
        pass

    def get_inflation_expectations_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """インフレ期待データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # プライマリ: ECB Data APIからデータ取得
        api_result = self._fetch_from_ecb()

        if api_result:
            next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, "Euro Area")

            cache_payload = {
                "data": api_result,
                "metadata": {
                    "source": "European Central Bank (ECB) - Consumer Expectations Survey",
                    "indicator": "CES - Inflation Expectations",
                    "data_start": "2020-01-01",
                    "description": "消費者インフレ期待（ユーロ圏・CES）",
                    "variables": {
                        "inflation_12m": "12ヶ月先インフレ期待（加重中央値）",
                        "inflation_3y": "3年先インフレ期待（加重中央値）",
                        "inflation_5y": "5年先インフレ期待（加重中央値）",
                    },
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result,
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
                "data": file_cache.get("data", {}),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": {},
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_ecb(self, start_date: str = "2020-01-01") -> Optional[Dict[str, List[Dict]]]:
        """ECB APIからCESデータを取得"""
        try:
            print("[ECBInflationExpectations] Fetching CES data from ECB API")

            result = {}

            for key, series_key in self.SERIES_KEYS.items():
                data = self._fetch_series_data(series_key, start_date)
                if data:
                    result[key] = data
                    print(f"[ECBInflationExpectations] {key}: {len(data)} data points")

            if not result:
                print("[ECBInflationExpectations] No data fetched from ECB API")
                return None

            return result

        except Exception as e:
            print(f"[ECBInflationExpectations] Error fetching from ECB: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_series_data(self, series_key: str, start_date: str) -> Optional[List[Dict]]:
        """単一シリーズをECB APIから取得"""
        url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/{series_key}"

        params = {
            "startPeriod": start_date,
            "format": "jsondata",
            "detail": "dataonly"
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECBInflationExpectations] No datasets for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECBInflationExpectations] No series in dataset for {series_key}")
                return None

            # 最初のシリーズを取得
            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            # 時間ディメンションを取得
            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print(f"[ECBInflationExpectations] No time dimension for {series_key}")
                return None

            time_values = time_dimension.get("values", [])

            # 結果リストを構築
            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    date_str = time_values[time_index].get("id")  # "2024-01" format
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None and date_str:
                        # 月次形式 "2024-01" を "2024-01-01" に変換
                        formatted_date = f"{date_str}-01"
                        result.append({
                            "date": formatted_date,
                            "value": round(float(value), 2)
                        })

            # 日付でソート
            result.sort(key=lambda x: x["date"])
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECBInflationExpectations] Request error for {series_key}: {e}")
            return None
        except Exception as e:
            print(f"[ECBInflationExpectations] Parse error for {series_key}: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMPパターン方式）"""
        return should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str, "Euro Area")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ECBInflationExpectations] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBInflationExpectations] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        data = cached_data.get("data", {}) if cached_data else {}

        return {
            "indicator": "ECB Consumer Inflation Expectations (CES)",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "inflation_12m": len(data.get("inflation_12m", [])),
                "inflation_3y": len(data.get("inflation_3y", [])),
                "inflation_5y": len(data.get("inflation_5y", [])),
            } if cached_data else {},
            "next_release": cached_data.get("next_release") if cached_data else get_next_release_by_pattern(self.FMP_EVENT_PATTERN, "Euro Area"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_inflation_expectations_service = ECBInflationExpectationsService()
