"""
ECB ユーロ圏調整済貸出サービス
ECB Data APIからユーロ圏の調整済貸出データを取得

指標:
- NFC (Non-Financial Corporations): 非金融法人向け調整済貸出
- Households (Total): 家計向け調整済貸出（総合）
- Households (House Purchase): 家計向け調整済貸出（住宅購入）

データソース:
- ECB Data API (BSI - Balance Sheet Items)
  - BSI.M.U2.Y.U.A20T.A.I.U2.2240.Z01.A (NFCs)
  - BSI.M.U2.Y.U.A20T.A.I.U2.2250.Z01.A (Households Total)
  - BSI.M.U2.Y.U.A22.A.I.U2.2250.Z01.A (Households House Purchase)

発表スケジュール:
- 月次発表（ECB統計カレンダーに基づく）
- https://www.ecb.europa.eu/press/calendars/statscal/mfm/html/stprmp.en.html

キャッシュ方式: ECB発表スケジュールベース更新 + 24時間TTL
"""
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import get_next_release_from_fmp


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_adjusted_loans_cache.json"


class ECBAdjustedLoansService:
    """ECB ユーロ圏調整済貸出サービス"""

    # ECB Legacy API（SDMX形式）- 安定したAPI
    ECB_LEGACY_API_BASE = "https://data-api.ecb.europa.eu/service/data"

    # シリーズキー（BSI = Balance Sheet Items）
    # M = Monthly
    # U2 = Euro Area
    # Y = Annual percentage changes (前年比変化率)
    # U = Unadjusted / A = Adjusted
    # A20T = Loans, total maturity, original maturity, all currencies
    # A = Index adjusted for sales and securitisation (adjusted)
    # I = MFI excluding Eurosystem
    # U2 = Euro area counterpart
    # 2240 = Non-financial corporations
    # 2250 = Households
    # Z01 = All sectors
    # A = All currencies
    SERIES_KEY_NFC = "M.U2.Y.U.A20T.A.I.U2.2240.Z01.A"           # 非金融法人向け
    SERIES_KEY_HOUSEHOLDS = "M.U2.Y.U.A20T.A.I.U2.2250.Z01.A"    # 家計向け（総合）
    SERIES_KEY_HOUSING = "M.U2.Y.U.A22.A.I.U2.2250.Z01.A"        # 家計向け（住宅購入）

    DATA_CACHE_KEY = "economy:ecb_adjusted_loans:data"
    ECONALPHA_ID = "ecb_adjusted_loans"

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
            print(f"[ECB Adjusted Loans] Fetching: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECB Adjusted Loans] No data sets found for {series_key}")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECB Adjusted Loans] No series found for {series_key}")
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
                print(f"[ECB Adjusted Loans] No time dimension found for {series_key}")
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
            print(f"[ECB Adjusted Loans] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB Adjusted Loans] Request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB Adjusted Loans] Parse error for {series_key}: {e}")
            return None

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日時を取得

        FMP APIを使用してM3マネーサプライ発表日時を取得
        （調整済貸出はM3と同時発表）
        """
        try:
            # FMP APIから次回発表日を取得（M3マネーサプライと同時発表）
            next_release = get_next_release_from_fmp(
                self.ECONALPHA_ID,
                patterns=["M3 Money Supply", "Monetary Developments"],
                country="EU"
            )
            if next_release:
                return next_release
        except Exception as e:
            print(f"[ECB Adjusted Loans] Error getting next release from FMP: {e}")

        return None

    def get_adjusted_loans_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECB調整済貸出データを取得（NFC・家計・住宅向け）"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = self._get_next_release()
                    return {
                        "nfc": cached_data.get("nfc", {}),
                        "households": cached_data.get("households", {}),
                        "housing": cached_data.get("housing", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIからデータ取得
        nfc_data = self._fetch_series_data(self.SERIES_KEY_NFC) or []
        households_data = self._fetch_series_data(self.SERIES_KEY_HOUSEHOLDS) or []
        housing_data = self._fetch_series_data(self.SERIES_KEY_HOUSING) or []

        has_data = len(nfc_data) > 0 or len(households_data) > 0 or len(housing_data) > 0

        if has_data:
            next_release = self._get_next_release()

            nfc_latest = nfc_data[-1] if nfc_data else None
            households_latest = households_data[-1] if households_data else None
            housing_latest = housing_data[-1] if housing_data else None

            cache_payload = {
                "nfc": {
                    "data": nfc_data,
                    "latest": nfc_latest,
                },
                "households": {
                    "data": households_data,
                    "latest": households_latest,
                },
                "housing": {
                    "data": housing_data,
                    "latest": housing_latest,
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "nfc": {
                    "data": nfc_data,
                    "latest": nfc_latest,
                },
                "households": {
                    "data": households_data,
                    "latest": households_latest,
                },
                "housing": {
                    "data": housing_data,
                    "latest": housing_latest,
                },
                "next_release": next_release,
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = self._get_next_release()
            return {
                "nfc": file_cache.get("nfc", {}),
                "households": file_cache.get("households", {}),
                "housing": file_cache.get("housing", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "nfc": {"data": [], "latest": None},
            "households": {"data": [], "latest": None},
            "housing": {"data": [], "latest": None},
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

            # 次回発表日時を過ぎていれば更新
            next_release = self._get_next_release()
            if next_release:
                release_datetime_str = next_release.get("datetime_jst")
                if release_datetime_str:
                    try:
                        release_dt = datetime.fromisoformat(release_datetime_str)
                        if last_updated < release_dt <= now:
                            return True
                    except Exception:
                        pass

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

        nfc_data = cached_data.get("nfc", {}) if cached_data else {}
        households_data = cached_data.get("households", {}) if cached_data else {}
        housing_data = cached_data.get("housing", {}) if cached_data else {}

        return {
            "indicator": "ECB Adjusted Loans to Euro Area",
            "source": "ECB Data API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "nfc_count": len(nfc_data.get("data", [])),
            "households_count": len(households_data.get("data", [])),
            "housing_count": len(housing_data.get("data", [])),
            "nfc_latest": nfc_data.get("latest"),
            "households_latest": households_data.get("latest"),
            "housing_latest": housing_data.get("latest"),
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_adjusted_loans_service = ECBAdjustedLoansService()
