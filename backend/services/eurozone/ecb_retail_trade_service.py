"""
ユーロ圏小売売上高サービス
Eurostat APIから Retail Trade Volume データを取得

指標:
- Retail Trade Volume Index - Euro Area 20
- 前月比 (MoM): 季節・稼働日調整済み
- 前年比 (YoY): 稼働日調整済み

データソース:
- Eurostat (European Statistical Office)
- Dataset: sts_trtu_m (Turnover and volume of sales in wholesale and retail trade)

発表スケジュール:
- 毎月2日〜12日 (CET)

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

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "eurozone" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_retail_trade_cache.json"


class ECBRetailTradeService:
    """ユーロ圏小売売上高サービス (Eurostat API)"""

    DATA_CACHE_KEY = "eurozone:retail_trade:data"
    ECONALPHA_ID = "ecb_retail_trade"
    FMP_EVENT_PATTERN = "Retail Sales"

    # Eurostat API設定
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
    DATASET = "sts_trtu_m"

    # Query parameters (6 dimensions: freq, indic_bt, nace_r2, s_adj, unit, geo)
    # M = Monthly
    # VOL_SLS = Volume of sales
    # G47 = Retail trade, except of motor vehicles and motorcycles
    # SCA = Seasonally and calendar adjusted data (for MoM)
    # CA = Calendar adjusted data only (for YoY)
    # I21 = Index, 2021=100
    # EA20 = Euro area - 20 countries
    SERIES_KEY_SCA = "M.VOL_SLS.G47.SCA.I21.EA20"  # 季節・営業日調整済み（前月比用）
    SERIES_KEY_CA = "M.VOL_SLS.G47.CA.I21.EA20"    # 営業日調整のみ（前年比用）

    def __init__(self):
        pass

    def get_ecb_retail_trade_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """小売売上高データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "retail_yoy": cached_data.get("retail_yoy", []),
                        "retail_mom": cached_data.get("retail_mom", []),
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
                "retail_yoy": api_result.get("retail_yoy", []),
                "retail_mom": api_result.get("retail_mom", []),
                "metadata": {
                    "source": "Eurostat",
                    "dataset": self.DATASET,
                    "indicator": "Retail Trade Volume Index - Euro Area 20",
                    "unit": "Percentage change",
                    "adjustment_mom": "Seasonally and calendar adjusted (SCA)",
                    "adjustment_yoy": "Calendar adjusted only (CA)",
                    "base_year": 2021,
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "retail_yoy": api_result.get("retail_yoy", []),
                "retail_mom": api_result.get("retail_mom", []),
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
                "retail_yoy": file_cache.get("retail_yoy", []),
                "retail_mom": file_cache.get("retail_mom", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "retail_yoy": [],
            "retail_mom": [],
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_eurostat(self) -> Optional[Dict[str, List[Dict]]]:
        """Eurostat APIからデータを取得"""
        # 季節・営業日調整済みデータ（前月比用）
        index_sca = self._fetch_eurostat_data(self.SERIES_KEY_SCA)
        # 営業日調整のみデータ（前年比用）
        index_ca = self._fetch_eurostat_data(self.SERIES_KEY_CA)

        if not index_sca and not index_ca:
            return None

        # 前月比を計算（SCAデータから）
        retail_mom = self._calculate_monthly_change(index_sca or [])
        # 前年比を計算（CAデータから）
        retail_yoy = self._calculate_year_on_year_change(index_ca or [])

        return {
            "retail_yoy": retail_yoy,
            "retail_mom": retail_mom,
        }

    def _fetch_eurostat_data(self, series_key: str, start_date: str = "2015-01") -> Optional[List[Dict]]:
        """Eurostat APIから指数データを取得"""
        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}/{series_key}"

        params = {
            "startPeriod": start_date,
            "format": "JSON"
        }

        try:
            print(f"[EurostatRetailTrade] Fetching data from Eurostat: {series_key}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Eurostat JSON形式を解析
            values = data.get("value", {})
            if not values:
                print("[EurostatRetailTrade] No values found in response")
                return None

            # 時間次元を取得
            time_dimension = data.get("dimension", {}).get("time", {})
            time_category = time_dimension.get("category", {})
            time_index = time_category.get("index", {})

            # index -> date のマッピングを作成
            index_to_date = {v: k for k, v in time_index.items()}

            # 結果リストを構築
            result = []
            for idx_str, value in values.items():
                idx = int(idx_str)
                date_str = index_to_date.get(idx)

                if date_str and value is not None:
                    result.append({
                        "date": date_str,
                        "value": float(value)
                    })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[EurostatRetailTrade] Fetched {len(result)} data points")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EurostatRetailTrade] Request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[EurostatRetailTrade] Parse error: {e}")
            return None

    def _calculate_year_on_year_change(self, index_data: List[Dict]) -> List[Dict]:
        """指数データから前年比を計算"""
        if not index_data or len(index_data) < 13:
            return []

        result = []
        for i in range(12, len(index_data)):
            current = index_data[i]
            year_ago = index_data[i - 12]

            if year_ago['value'] is not None and current['value'] is not None and year_ago['value'] != 0:
                yoy_change = ((current['value'] - year_ago['value']) / year_ago['value']) * 100
                result.append({
                    'date': current['date'],
                    'value': round(yoy_change, 2)
                })

        return result

    def _calculate_monthly_change(self, index_data: List[Dict]) -> List[Dict]:
        """指数データから前月比を計算"""
        if not index_data or len(index_data) < 2:
            return []

        result = []
        for i in range(1, len(index_data)):
            current = index_data[i]
            previous = index_data[i - 1]

            if previous['value'] is not None and current['value'] is not None and previous['value'] != 0:
                mom_change = ((current['value'] - previous['value']) / previous['value']) * 100
                result.append({
                    'date': current['date'],
                    'value': round(mom_change, 2)
                })

        return result

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
            print(f"[ECBRetailTrade] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBRetailTrade] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Eurozone Retail Trade",
            "source": "Eurostat API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "retail_yoy_count": len(cached_data.get("retail_yoy", [])) if cached_data else 0,
            "retail_mom_count": len(cached_data.get("retail_mom", [])) if cached_data else 0,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_retail_trade_service = ECBRetailTradeService()
