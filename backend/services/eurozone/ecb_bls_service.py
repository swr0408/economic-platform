"""
ECB BLS (Bank Lending Survey) サービス
ECB Data APIからユーロ圏銀行貸出調査データを取得

指標:
- Credit Standards - Enterprises (企業向け融資の信用基準)
- Credit Standards - Households (家計向け融資の信用基準)

キー構造:
- BLS = Bank Lending Survey
- Q = Quarterly
- U2 = Euro Area
- ALL = All banks
- O = Outstanding amounts
- E = Expected
- Z = All
- B3 = Enterprises
- F3 = Households for house purchase
- ZZ = All
- D = Diffusion index
- WFNET = Weighted net percentage

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
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_bls_cache.json"


class ECBBLSService:
    """ECB BLSサービス"""

    # ECB Data API
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "BLS"

    # シリーズキー（信用基準）
    SERIES_KEY_ENTERPRISES = "Q.U2.ALL.O.E.Z.B3.ZZ.D.WFNET"  # 企業向け
    SERIES_KEY_HOUSEHOLDS = "Q.U2.ALL.O.E.Z.F3.ZZ.D.WFNET"   # 家計向け

    DATA_CACHE_KEY = "economy:ecb_bls:data"
    ECONALPHA_ID = "ecb_bls"

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
            print(f"[ECB BLS] Fetching: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECB BLS] No data sets found for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECB BLS] No series found for {series_key}")
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
                print(f"[ECB BLS] No time dimension found for {series_key}")
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
            print(f"[ECB BLS] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB BLS] Request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB BLS] Parse error for {series_key}: {e}")
            return None

    def get_ecb_bls_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECB BLSデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "enterprises": cached_data.get("enterprises", []),
                        "households": cached_data.get("households", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIからデータ取得
        enterprises_data = self._fetch_series_data(self.SERIES_KEY_ENTERPRISES) or []
        households_data = self._fetch_series_data(self.SERIES_KEY_HOUSEHOLDS) or []

        # 少なくとも1つにデータがあれば成功
        has_data = len(enterprises_data) > 0 or len(households_data) > 0

        if has_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            metadata = {
                "last_updated": datetime.now(JST).isoformat(),
                "source": "European Central Bank (ECB) - Bank Lending Survey",
                "data_start": "2015-01-01",
                "unit": "Net percentage",
                "frequency": "Quarterly",
                "description": {
                    "enterprises": "Credit standards for loans to enterprises (企業向け融資の信用基準)",
                    "households": "Credit standards for loans to households for house purchase (家計向け住宅融資の信用基準)"
                }
            }

            cache_payload = {
                "enterprises": enterprises_data,
                "households": households_data,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "enterprises": enterprises_data,
                "households": households_data,
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
                "enterprises": file_cache.get("enterprises", []),
                "households": file_cache.get("households", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "enterprises": [],
            "households": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 24時間以上経過していれば更新
            if (now - last_updated) > timedelta(hours=24):
                return True

            return False
        except Exception:
            return True

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
            "indicator": "ECB BLS",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "enterprises_count": len(cached_data.get("enterprises", [])) if cached_data else 0,
            "households_count": len(cached_data.get("households", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_bls_service = ECBBLSService()
