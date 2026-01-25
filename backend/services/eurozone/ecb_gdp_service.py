"""
ECB GDP (Gross Domestic Product) サービス
ECB Data APIからユーロ圏GDPデータを取得

指標:
- GDP成長率（前期比）: MNA.Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.G1
- GDP成長率（前年比）: MNA.Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.GY

キー構造:
- MNA = Main National Accounts
- Q = Quarterly
- Y = Annual data
- I9 = Euro Area
- W2 = Working day and seasonally adjusted
- S1 = Total economy
- S1 = All sectors
- B = Balancing item
- B1GQ = Gross domestic product at market prices
- EUR = Euro
- LR = Chain linked volumes, index 2010=100
- G1 = Growth rate to previous period (QoQ)
- GY = Growth rate to same period in previous year (YoY)

発表スケジュール:
- 毎日18:00 CET（冬時間）/ 19:00 CEST（夏時間）

キャッシュ方式: 日次更新
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
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_gdp_cache.json"


class ECBGDPService:
    """ECB GDP サービス"""

    # ECB Data API
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "MNA"

    # シリーズキー
    SERIES_KEY_QOQ = "Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.G1"
    SERIES_KEY_YOY = "Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.GY"

    DATA_CACHE_KEY = "economy:ecb_gdp:data"
    ECONALPHA_ID = "euro_gdp"

    # FMPイベントパターン（次回発表日取得・更新判定用）
    FMP_EVENT_PATTERN = "GDP Growth Rate"

    def __init__(self):
        pass

    def _fetch_series_data(self, series_key: str, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """ECB APIから単一シリーズデータを取得"""
        url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/{series_key}"
        params = {
            "startPeriod": start_date,
            "format": "jsondata"
        }

        try:
            print(f"[ECB GDP] Fetching: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECB GDP] No data sets found for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECB GDP] No series found for {series_key}")
                return None

            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print(f"[ECB GDP] No time dimension found for {series_key}")
                return None

            time_values = time_dimension.get("values", [])

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

            result.sort(key=lambda x: x["date"])
            print(f"[ECB GDP] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB GDP] Request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB GDP] Parse error for {series_key}: {e}")
            return None

    def get_ecb_gdp_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECB GDPデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "gdp_growth_qoq": cached_data.get("gdp_growth_qoq", []),
                        "gdp_growth_yoy": cached_data.get("gdp_growth_yoy", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIからデータ取得
        gdp_growth_qoq = self._fetch_series_data(self.SERIES_KEY_QOQ) or []
        gdp_growth_yoy = self._fetch_series_data(self.SERIES_KEY_YOY) or []

        if gdp_growth_qoq or gdp_growth_yoy:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            metadata = {
                "last_updated": datetime.now(JST).isoformat(),
                "source": "European Central Bank (ECB) - Main National Accounts",
                "data_start": "2015-01-01",
                "unit_qoq": "Growth rate to previous period (%)",
                "unit_yoy": "Growth rate to same period in previous year (%)",
                "frequency": "Quarterly"
            }

            cache_payload = {
                "gdp_growth_qoq": gdp_growth_qoq,
                "gdp_growth_yoy": gdp_growth_yoy,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "gdp_growth_qoq": gdp_growth_qoq,
                "gdp_growth_yoy": gdp_growth_yoy,
                "metadata": metadata,
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            return {
                "gdp_growth_qoq": file_cache.get("gdp_growth_qoq", []),
                "gdp_growth_yoy": file_cache.get("gdp_growth_yoy", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "gdp_growth_qoq": [],
            "gdp_growth_yoy": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMPパターン方式）"""
        return should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str, "EU")

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
            "indicator": "ECB GDP",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "qoq_count": len(cached_data.get("gdp_growth_qoq", [])) if cached_data else 0,
            "yoy_count": len(cached_data.get("gdp_growth_yoy", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_gdp_service = ECBGDPService()
