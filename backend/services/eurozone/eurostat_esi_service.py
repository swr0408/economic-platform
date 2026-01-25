"""
Eurostat ESI (Economic Sentiment Indicator) サービス
Eurostat APIからESIデータを取得

指標:
- Economic Sentiment Indicator (ESI) - ユーロ圏・ドイツ・フランス・イタリア
- Dataset: ei_bssi_m_r2
- 指数形式（100 = 中立）

データソース:
- Eurostat Business and Consumer Surveys
- https://ec.europa.eu/eurostat/databrowser/view/ei_bssi_m_r2/default/table

発表スケジュール:
- 毎月25日〜翌月8日 18:00-18:10 CET

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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eurostat_esi_cache.json"


class EurostatESIService:
    """Eurostat ESI (Economic Sentiment Indicator) サービス"""

    DATA_CACHE_KEY = "eurozone:esi:data"
    ECONALPHA_ID = "euro_esi"
    FMP_EVENT_PATTERN = "Economic Sentiment"

    # Eurostat API設定
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
    DATASET = "ei_bssi_m_r2"

    # 地域コード
    GEO_CODES = {
        "euro_area": "EA20",
        "germany": "DE",
        "france": "FR",
        "italy": "IT",
    }

    # ESI指標コード（指数形式）
    INDIC = "BS-ESI-I"
    S_ADJ = "SA"
    FREQ = "M"

    def __init__(self):
        pass

    def get_eurostat_esi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ESIデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "euro_area": cached_data.get("euro_area", []),
                        "germany": cached_data.get("germany", []),
                        "france": cached_data.get("france", []),
                        "italy": cached_data.get("italy", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # Eurostat APIから取得
        api_result = self._fetch_from_eurostat()
        if api_result:
            next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN)

            cache_payload = {
                "euro_area": api_result.get("euro_area", []),
                "germany": api_result.get("germany", []),
                "france": api_result.get("france", []),
                "italy": api_result.get("italy", []),
                "metadata": {
                    "source": "Eurostat - Business and Consumer Surveys",
                    "dataset": self.DATASET,
                    "indicator": "Economic Sentiment Indicator (ESI)",
                    "unit": "Index (100 = neutral)",
                    "frequency": "Monthly",
                    "seasonal_adjustment": "Seasonally adjusted",
                    "countries": {
                        "euro_area": "Euro Area - 20 countries",
                        "germany": "Germany",
                        "france": "France",
                        "italy": "Italy",
                    },
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "euro_area": api_result.get("euro_area", []),
                "germany": api_result.get("germany", []),
                "france": api_result.get("france", []),
                "italy": api_result.get("italy", []),
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "eurostat_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "euro_area": file_cache.get("euro_area", []),
                "germany": file_cache.get("germany", []),
                "france": file_cache.get("france", []),
                "italy": file_cache.get("italy", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "euro_area": [],
            "germany": [],
            "france": [],
            "italy": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_eurostat(self) -> Optional[Dict[str, List[Dict]]]:
        """Eurostat APIからデータを取得"""
        result = {}

        for region_key, geo_code in self.GEO_CODES.items():
            data = self._fetch_country_data(geo_code)
            if data:
                result[region_key] = data
            else:
                result[region_key] = []

        if any(result.values()):
            return result
        return None

    def _fetch_country_data(self, geo_code: str, start_period: str = "2015-01") -> Optional[List[Dict]]:
        """特定の国/地域のデータを取得"""
        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}/"

        params = {
            "format": "JSON",
            "startPeriod": start_period,
            "freq": self.FREQ,
            "indic": self.INDIC,
            "s_adj": self.S_ADJ,
            "geo": geo_code,
        }

        try:
            print(f"[EurostatESI] Fetching data for {geo_code}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # 次元とデータを抽出
            dimensions = data.get("dimension", {})
            size = data.get("size", [])
            values = data.get("value", {})

            # 時間次元を取得
            time_dim = dimensions.get("time", {})
            time_category = time_dim.get("category", {})
            time_index = time_category.get("index", {})

            # 地理次元を取得
            geo_dim = dimensions.get("geo", {})
            geo_category = geo_dim.get("category", {})
            geo_index_map = geo_category.get("index", {})

            if not time_index or not values or geo_code not in geo_index_map:
                print(f"[EurostatESI] No data found for {geo_code}")
                return None

            geo_position = geo_index_map[geo_code]

            result = []

            if len(size) >= 5:
                # 指標位置を取得
                indic_dim = dimensions.get("indic", {})
                indic_index_map = indic_dim.get("category", {}).get("index", {})
                indic_position = indic_index_map.get(self.INDIC, 0)

                # 季節調整位置を取得
                s_adj_dim = dimensions.get("s_adj", {})
                s_adj_index_map = s_adj_dim.get("category", {}).get("index", {})
                s_adj_position = s_adj_index_map.get(self.S_ADJ, 0)

                # 次元サイズ
                time_size = size[4]
                geo_size = size[3]
                s_adj_size = size[2]

                for time_period, time_pos in time_index.items():
                    # 多次元インデックスを計算
                    multi_index = (
                        indic_position * (s_adj_size * geo_size * time_size)
                        + s_adj_position * (geo_size * time_size)
                        + geo_position * time_size
                        + time_pos
                    )
                    value = values.get(str(multi_index))

                    if value is not None:
                        result.append({
                            "date": time_period,
                            "value": round(float(value), 1),
                        })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[EurostatESI] Fetched {len(result)} data points for {geo_code}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EurostatESI] Request error for {geo_code}: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            print(f"[EurostatESI] Parse error for {geo_code}: {e}")
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
            print(f"[EurostatESI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EurostatESI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Eurostat ESI",
            "source": "Eurostat API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "euro_area_count": len(cached_data.get("euro_area", [])) if cached_data else 0,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
eurostat_esi_service = EurostatESIService()
