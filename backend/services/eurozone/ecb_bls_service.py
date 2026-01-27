"""
ECB BLS (Bank Lending Survey) サービス
ECB Data APIからユーロ圏銀行貸出調査データを取得

指標:
- Credit Standards - Enterprises (企業向け融資の信用基準)
- Credit Standards - Households (家計向け融資の信用基準)
- Credit Demand - Enterprises (企業向け融資の信用需要)
- Credit Demand - Households (家計向け融資の信用需要)

キー構造:
- BLS = Bank Lending Survey
- Q = Quarterly
- U2 = Euro Area
- ALL = All banks
- O = Outstanding amounts (信用基準)
- Z = All
- H = Households / Credit demand
- C = Credit
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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_bls_cache.json"


class ECBBLSService:
    """ECB BLSサービス"""

    # ECB Data Portal API (新エンドポイント)
    # https://data.ecb.europa.eu/data/datasets/BLS/BLS.Q.U2.ALL.O.E.Z.B3.ZZ.D.WFNET
    # https://data.ecb.europa.eu/data/datasets/BLS/BLS.Q.U2.ALL.O.E.Z.F3.ZZ.D.WFNET
    ECB_API_BASE = "https://data.ecb.europa.eu/data-detail-api"
    DATAFLOW = "BLS"

    # シリーズキー（企業向け融資 - Enterprises）
    # B3 = 現在（Backward looking）, F3 = 予想（Forward looking）
    SERIES_KEY_DEMAND_ENTERPRISES_CURRENT = "BLS.Q.U2.ALL.O.E.Z.B3.ZZ.D.WFNET"   # 現在の信用需要 - 企業向け融資
    SERIES_KEY_DEMAND_ENTERPRISES_EXPECTED = "BLS.Q.U2.ALL.O.E.Z.F3.ZZ.D.WFNET"  # 予想信用需要 - 企業向け融資

    # シリーズキー（消費者信用 - Consumer Credit）
    # B3 = 現在（Backward looking）, F3 = 予想（Forward looking）
    SERIES_KEY_DEMAND_CONSUMER_CURRENT = "BLS.Q.U2.ALL.Z.H.C.B3.ZZ.D.WFNET"      # 現在の信用需要 - 消費者信用
    SERIES_KEY_DEMAND_CONSUMER_EXPECTED = "BLS.Q.U2.ALL.Z.H.C.F3.ZZ.D.WFNET"     # 期待信用需要 - 消費者信用

    # シリーズキー（住宅購入向け融資 - Loans to Households for House Purchase）
    # B3 = 現在（Backward looking）, F3 = 予想（Forward looking）
    SERIES_KEY_DEMAND_HOUSING_CURRENT = "BLS.Q.U2.ALL.Z.H.H.B3.ZZ.D.WFNET"       # 現在の信用需要 - 住宅購入向け融資
    SERIES_KEY_DEMAND_HOUSING_EXPECTED = "BLS.Q.U2.ALL.Z.H.H.F3.ZZ.D.WFNET"      # 期待信用需要 - 住宅購入向け融資

    DATA_CACHE_KEY = "economy:ecb_bls:data"
    ECONALPHA_ID = "ecb_bls"

    def __init__(self):
        pass

    def _fetch_series_data(self, series_key: str, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """ECB Data Portal APIから単一シリーズデータを取得"""
        # 新しいECB Data Portal APIを使用
        url = f"{self.ECB_API_BASE}/{series_key}"

        try:
            print(f"[ECB BLS] Fetching: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            # 新APIのレスポンス形式に対応
            # レスポンスは直接配列: [{"PERIOD": "2025-10-01", "OBS_VALUE_AS_IS": "1.925...", ...}, ...]
            # または { "data": [...] } 形式の場合もある
            if isinstance(data, list):
                raw_data = data
            elif isinstance(data, dict) and "data" in data:
                raw_data = data["data"]
            else:
                print(f"[ECB BLS] Unexpected response format for {series_key}")
                return None

            if not raw_data:
                print(f"[ECB BLS] Empty data for {series_key}")
                return None

            result = []
            for item in raw_data:
                # 日付は PERIOD フィールド（2025-10-01形式）から四半期形式に変換
                period_raw = item.get("PERIOD") or item.get("TIME_PERIOD")
                period_name = item.get("PERIOD_NAME")  # "Q4 2025" 形式

                # OBS_VALUE_AS_IS から値を取得（文字列で格納されている）
                value_str = item.get("OBS_VALUE_AS_IS") or item.get("OBS_VALUE") or item.get("VALUE")

                # 日付を四半期形式に変換
                if period_name:
                    # "Q4 2025" -> "2025-Q4"
                    parts = period_name.split()
                    if len(parts) == 2:
                        period = f"{parts[1]}-{parts[0]}"
                    else:
                        period = period_raw
                elif period_raw:
                    # "2025-10-01" -> "2025-Q4"
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(period_raw[:10], "%Y-%m-%d")
                        quarter = (dt.month - 1) // 3 + 1
                        period = f"{dt.year}-Q{quarter}"
                    except:
                        period = period_raw
                else:
                    continue

                if period and value_str is not None:
                    try:
                        value = float(value_str)
                        # 期間をフィルタリング（start_date以降のみ）
                        if period >= start_date[:4]:  # 年で比較
                            result.append({
                                "date": period,
                                "value": value
                            })
                    except (ValueError, TypeError):
                        continue

            result.sort(key=lambda x: x["date"])
            print(f"[ECB BLS] Fetched {len(result)} data points for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB BLS] Request error for {series_key}: {e}")
            # フォールバック: 旧APIを試す
            return self._fetch_series_data_legacy(series_key, start_date)
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB BLS] Parse error for {series_key}: {e}")
            return self._fetch_series_data_legacy(series_key, start_date)

    def _fetch_series_data_legacy(self, series_key: str, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """旧ECB APIから単一シリーズデータを取得（フォールバック）"""
        # 旧形式のシリーズキー（BLS.プレフィックスを除去）
        legacy_key = series_key.replace("BLS.", "") if series_key.startswith("BLS.") else series_key
        url = f"https://data-api.ecb.europa.eu/service/data/BLS/{legacy_key}"
        params = {
            "startPeriod": start_date,
            "format": "jsondata"
        }

        try:
            print(f"[ECB BLS] Fetching (legacy): {url}")
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
            print(f"[ECB BLS] Fetched {len(result)} data points (legacy) for {series_key}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB BLS] Legacy request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB BLS] Legacy parse error for {series_key}: {e}")
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
                        "enterprises_current": cached_data.get("enterprises_current", []),
                        "enterprises_expected": cached_data.get("enterprises_expected", []),
                        "consumer_current": cached_data.get("consumer_current", []),
                        "consumer_expected": cached_data.get("consumer_expected", []),
                        "housing_current": cached_data.get("housing_current", []),
                        "housing_expected": cached_data.get("housing_expected", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIからデータ取得（企業向け融資）
        enterprises_current_data = self._fetch_series_data(self.SERIES_KEY_DEMAND_ENTERPRISES_CURRENT) or []
        enterprises_expected_data = self._fetch_series_data(self.SERIES_KEY_DEMAND_ENTERPRISES_EXPECTED) or []

        # ECB APIからデータ取得（消費者信用）
        consumer_current_data = self._fetch_series_data(self.SERIES_KEY_DEMAND_CONSUMER_CURRENT) or []
        consumer_expected_data = self._fetch_series_data(self.SERIES_KEY_DEMAND_CONSUMER_EXPECTED) or []

        # ECB APIからデータ取得（住宅購入向け融資）
        housing_current_data = self._fetch_series_data(self.SERIES_KEY_DEMAND_HOUSING_CURRENT) or []
        housing_expected_data = self._fetch_series_data(self.SERIES_KEY_DEMAND_HOUSING_EXPECTED) or []

        # 少なくとも1つにデータがあれば成功
        has_data = (len(enterprises_current_data) > 0 or len(enterprises_expected_data) > 0 or
                    len(consumer_current_data) > 0 or len(consumer_expected_data) > 0 or
                    len(housing_current_data) > 0 or len(housing_expected_data) > 0)

        if has_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            metadata = {
                "last_updated": datetime.now(JST).isoformat(),
                "source": "European Central Bank (ECB) - Bank Lending Survey",
                "data_start": "2015-01-01",
                "unit": "Net percentage",
                "frequency": "Quarterly",
                "description": {
                    "enterprises_current": "Loan demand - Enterprises (現在の信用需要 - 企業向け融資)",
                    "enterprises_expected": "Loan demand - Enterprises expected (予想信用需要 - 企業向け融資)",
                    "consumer_current": "Loan demand - Consumer credit (現在の信用需要 - 消費者信用)",
                    "consumer_expected": "Loan demand - Consumer credit expected (期待信用需要 - 消費者信用)",
                    "housing_current": "Loan demand - Households for house purchase (現在の信用需要 - 住宅購入向け融資)",
                    "housing_expected": "Loan demand - Households for house purchase expected (期待信用需要 - 住宅購入向け融資)"
                }
            }

            cache_payload = {
                "enterprises_current": enterprises_current_data,
                "enterprises_expected": enterprises_expected_data,
                "consumer_current": consumer_current_data,
                "consumer_expected": consumer_expected_data,
                "housing_current": housing_current_data,
                "housing_expected": housing_expected_data,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "enterprises_current": enterprises_current_data,
                "enterprises_expected": enterprises_expected_data,
                "consumer_current": consumer_current_data,
                "consumer_expected": consumer_expected_data,
                "housing_current": housing_current_data,
                "housing_expected": housing_expected_data,
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
                "enterprises_current": file_cache.get("enterprises_current", []),
                "enterprises_expected": file_cache.get("enterprises_expected", []),
                "consumer_current": file_cache.get("consumer_current", []),
                "consumer_expected": file_cache.get("consumer_expected", []),
                "housing_current": file_cache.get("housing_current", []),
                "housing_expected": file_cache.get("housing_expected", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "enterprises_current": [],
            "enterprises_expected": [],
            "consumer_current": [],
            "consumer_expected": [],
            "housing_current": [],
            "housing_expected": [],
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
            "enterprises_current_count": len(cached_data.get("enterprises_current", [])) if cached_data else 0,
            "enterprises_expected_count": len(cached_data.get("enterprises_expected", [])) if cached_data else 0,
            "consumer_current_count": len(cached_data.get("consumer_current", [])) if cached_data else 0,
            "consumer_expected_count": len(cached_data.get("consumer_expected", [])) if cached_data else 0,
            "housing_current_count": len(cached_data.get("housing_current", [])) if cached_data else 0,
            "housing_expected_count": len(cached_data.get("housing_expected", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_bls_service = ECBBLSService()
