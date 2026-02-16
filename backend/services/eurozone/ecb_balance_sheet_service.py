"""
ECBバランスシートサービス
ECB Data APIからECB総資産データを取得（ILMデータセット）

指標:
- ECB Total Assets: ECB総資産（百万ユーロ）

データソース:
- ECB Legacy API (SDMX): ILM/W.U2.C.T000000.Z5.Z01
  - W = Weekly
  - U2 = Euro Area
  - C = Consolidated
  - T000000 = Total Assets/Liabilities
  - Z5 = All instruments
  - Z01 = All maturities

発表スケジュール:
- 週次（毎週火曜日）

キャッシュ方式: 24時間ベース（FMPマッピングなし）
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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_balance_sheet_cache.json"


class ECBBalanceSheetService:
    """ECBバランスシート（総資産）サービス"""

    # ECB Legacy API（SDMX形式）
    ECB_LEGACY_API_BASE = "https://data-api.ecb.europa.eu/service/data"

    # シリーズキー（ILMデータセット）
    # W.U2.C.T000000.Z5.Z01 = Weekly, Euro Area, Consolidated, Total Assets
    SERIES_KEY = "W.U2.C.T000000.Z5.Z01"

    DATA_CACHE_KEY = "monetary_policy:ecb_balance_sheet:data"

    def __init__(self):
        pass

    def _fetch_series_data(self, start_date: str = "2007-01") -> Optional[List[Dict]]:
        """ECB Legacy API（SDMX）からシリーズデータを取得"""
        url = f"{self.ECB_LEGACY_API_BASE}/ILM/{self.SERIES_KEY}"
        params = {
            "startPeriod": start_date,
            "format": "jsondata"
        }

        try:
            print(f"[ECB BalanceSheet] Fetching: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECB BalanceSheet] No data sets found")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECB BalanceSheet] No series found")
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
                print(f"[ECB BalanceSheet] No time dimension found")
                return None

            time_values = time_dimension.get("values", [])

            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    period = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None and period:
                        # 週次データ: "2024-W01" → 月曜日の日付に変換
                        date_str = self._week_to_date(period)
                        if date_str:
                            result.append({
                                "date": date_str,
                                "value": float(value)
                            })

            result.sort(key=lambda x: x["date"])
            print(f"[ECB BalanceSheet] Fetched {len(result)} data points")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB BalanceSheet] Request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB BalanceSheet] Parse error: {e}")
            return None

    def _week_to_date(self, week_str: str) -> Optional[str]:
        """週番号文字列をISO日付に変換（例: "2024-W01" → "2024-01-01"）"""
        try:
            # ISO 8601: %G=ISO year, %V=ISO week, %u=weekday (1=Monday)
            dt = datetime.strptime(f"{week_str}-1", "%G-W%V-%u")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    def get_ecb_balance_sheet_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECBバランスシートデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ECB APIからデータ取得
        fetched_data = self._fetch_series_data() or []

        if fetched_data:
            latest = fetched_data[-1] if fetched_data else None

            cache_payload = {
                "data": fetched_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": fetched_data,
                "latest": latest,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（24時間ベース）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() > 86400
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
            "indicator": "ECB Balance Sheet (Total Assets)",
            "source": "ECB Data API (ILM)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_balance_sheet_service = ECBBalanceSheetService()
