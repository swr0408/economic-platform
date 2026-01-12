"""
ECB GDP Components (構成要素別寄与度) サービス
ECB Data APIからユーロ圏GDP構成要素データを取得

指標:
- Private Consumption (民間消費)
- Government Consumption (政府消費)
- Gross Fixed Capital Formation (総固定資本形成)
- Changes in Inventories (在庫変動)
- Net Exports (純輸出)

キー構造:
- MNA = Main National Accounts
- Q = Quarterly
- Y = Annual data
- I9 = Euro Area
- W0/W1 = Different adjustment methods
- EUR_R_B1GQ = Real GDP contribution
- Y.GO1 = Growth contribution (percentage points)

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


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_gdp_components_cache.json"


class ECBGDPComponentsService:
    """ECB GDP構成要素サービス"""

    # ECB Data API
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "MNA"

    # シリーズキー（GDP寄与度）
    SERIES_KEYS = {
        "private_consumption": "Q.Y.I9.W0.S1M.S1.D.P31._Z._Z._T.EUR_R_B1GQ.Y.GO1",
        "government_consumption": "Q.Y.I9.W0.S13.S1.D.P3._Z._Z._T.EUR_R_B1GQ.Y.GO1",
        "gross_fixed_capital": "Q.Y.I9.W0.S1.S1.D.P51G.N11G._T._Z.EUR_R_B1GQ.Y.GO1",
        "changes_in_inventories": "Q.Y.I9.W0.S1.S1.D.P5M.N1MG._T._Z.EUR_R_B1GQ.Y.GO1",
        "net_exports": "Q.Y.I9.W1.S1.S1.B.B11._Z._Z._Z.EUR_R_B1GQ.Y.GO1"
    }

    DATA_CACHE_KEY = "economy:ecb_gdp_components:data"

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
            print(f"[ECB GDP Components] Fetching: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECB GDP Components] No data sets found for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECB GDP Components] No series found for {series_key}")
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
                print(f"[ECB GDP Components] No time dimension found for {series_key}")
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
            print(f"[ECB GDP Components] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB GDP Components] Request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB GDP Components] Parse error for {series_key}: {e}")
            return None

    def get_ecb_gdp_components_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECB GDP構成要素データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "components": cached_data.get("components", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIからデータ取得
        components_data = {}
        for component_name, series_key in self.SERIES_KEYS.items():
            data = self._fetch_series_data(series_key)
            components_data[component_name] = data or []

        # 少なくとも1つのコンポーネントにデータがあれば成功
        has_data = any(len(v) > 0 for v in components_data.values())

        if has_data:
            metadata = {
                "last_updated": datetime.now(JST).isoformat(),
                "source": "European Central Bank (ECB) - Main National Accounts",
                "data_start": "2015-01-01",
                "unit": "Contribution to GDP growth (percentage points)",
                "frequency": "Quarterly",
                "components": {
                    "private_consumption": "Private Consumption (民間消費)",
                    "government_consumption": "Government Consumption (政府消費)",
                    "gross_fixed_capital": "Gross Fixed Capital Formation (総固定資本形成)",
                    "changes_in_inventories": "Changes in Inventories (在庫変動)",
                    "net_exports": "Net Exports (純輸出)"
                }
            }

            cache_payload = {
                "components": components_data,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "components": components_data,
                "metadata": metadata,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "components": file_cache.get("components", {}),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "components": {},
            "metadata": {},
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

        component_counts = {}
        if cached_data and "components" in cached_data:
            for key, values in cached_data["components"].items():
                component_counts[key] = len(values) if values else 0

        return {
            "indicator": "ECB GDP Components",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "component_counts": component_counts,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_gdp_components_service = ECBGDPComponentsService()
