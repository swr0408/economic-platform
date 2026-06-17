"""
ECB M3マネーサプライサービス
ECB Data APIからM3マネーサプライデータを取得

指標:
- M3 Money Supply YoY: M3マネーサプライ前年比（%）
- M3 Money Supply Level: M3マネーサプライ原数値（10億ユーロ）

データソース:
- ECB Legacy API (前年比): BSI/M.U2.Y.V.M30.X.I.U2.2300.Z01.A
- ECB Legacy API (原数値): BSI/M.U2.N.V.M30.X.I.U2.2300.Z01.E

発表スケジュール:
- 月次発表（不定期、毎月下旬）

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


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_m3_cache.json"


class ECBM3Service:
    """ECB M3マネーサプライサービス"""

    # ECB Legacy API（SDMX形式）- 新APIより安定している
    ECB_LEGACY_API_BASE = "https://data-api.ecb.europa.eu/service/data"

    # シリーズキー（Legacy API用 - BSI.プレフィックスなし）
    # BSI = Balance Sheet Items
    # M = Monthly
    # U2 = Euro Area
    # Y = Annual percentage changes (前年比変化率)
    # N = Index (原数値/指数)
    # V = Outstanding amounts at the end of the period (stocks)
    # M30 = M3
    # X = All currencies combined
    # I = MFI sector (excl. Eurosystem)
    # U2 = Euro area
    # 2300 = Total
    # Z01 = All counterpart sectors
    # A = All currencies (前年比用)
    # E = Euro (原数値用)
    SERIES_KEY_YOY = "M.U2.Y.V.M30.X.I.U2.2300.Z01.A"      # 前年比（%）
    SERIES_KEY_LEVEL = "M.U2.N.V.M30.X.I.U2.2300.Z01.E"    # 原数値（10億ユーロ）

    DATA_CACHE_KEY = "monetary_policy:ecb_m3:data"
    ECONALPHA_ID = "monetary_aggregate_m3"

    def __init__(self):
        pass

    def _fetch_series_data(self, series_key: str, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """ECB Legacy API（SDMX）からシリーズデータを取得"""
        url = f"{self.ECB_LEGACY_API_BASE}/BSI/{series_key}"
        params = {
            "startPeriod": start_date,
            "format": "jsondata"
        }

        try:
            print(f"[ECB M3] Fetching: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECB M3] No data sets found for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECB M3] No series found for {series_key}")
                return None

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
                print(f"[ECB M3] No time dimension found for {series_key}")
                return None

            time_values = time_dimension.get("values", [])

            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    period = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None and period:
                        # 日付を月初形式に変換（2024-01 → 2024-01-01）
                        date_str = f"{period}-01" if len(period) == 7 else period
                        result.append({
                            "date": date_str,
                            "value": float(value)
                        })

            result.sort(key=lambda x: x["date"])
            print(f"[ECB M3] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB M3] Request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB M3] Parse error for {series_key}: {e}")
            return None

    def get_ecb_m3_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECB M3マネーサプライデータを取得（原数値と前年比）"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "yoy": cached_data.get("yoy", {}),
                        "level": cached_data.get("level", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIからデータ取得（前年比と原数値）
        yoy_data = self._fetch_series_data(self.SERIES_KEY_YOY) or []
        level_data = self._fetch_series_data(self.SERIES_KEY_LEVEL) or []

        has_data = len(yoy_data) > 0 or len(level_data) > 0

        if has_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            yoy_latest = yoy_data[-1] if yoy_data else None
            level_latest = level_data[-1] if level_data else None

            cache_payload = {
                "yoy": {
                    "data": yoy_data,
                    "latest": yoy_latest,
                },
                "level": {
                    "data": level_data,
                    "latest": level_latest,
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "yoy": {
                    "data": yoy_data,
                    "latest": yoy_latest,
                },
                "level": {
                    "data": level_data,
                    "latest": level_latest,
                },
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
                "yoy": file_cache.get("yoy", {}),
                "level": file_cache.get("level", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "yoy": {"data": [], "latest": None},
            "level": {"data": [], "latest": None},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

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

        yoy_data = cached_data.get("yoy", {}) if cached_data else {}
        level_data = cached_data.get("level", {}) if cached_data else {}

        return {
            "indicator": "ECB M3 Money Supply",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "yoy_count": len(yoy_data.get("data", [])),
            "level_count": len(level_data.get("data", [])),
            "yoy_latest": yoy_data.get("latest"),
            "level_latest": level_data.get("latest"),
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_m3_service = ECBM3Service()
