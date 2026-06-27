"""
ECB PPI (Producer Price Index) サービス
ユーロ圏生産者物価指数データを取得

指標:
- PPI: 生産者物価指数（建設を除く産業）

データソース:
- Eurostat API (sts_inppd_m) - プライマリ（より早く更新される）
- ECB Data API (STS) - フォールバック

発表スケジュール:
- 発表: 毎月1日〜8日 18:00-18:10 CET (冬時間: 19:00-19:10 JST)

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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_ppi_cache.json"


class ECBPPIService:
    """ECB PPIサービス"""

    DATA_CACHE_KEY = "eurozone:ecb_ppi:data"
    ECONALPHA_ID = "ecb_ppi"
    FMP_EVENT_PATTERNS = ["Producer Price Index MoM", "Producer Price Index YoY"]
    FMP_COUNTRY = "EU"

    # Eurostat API設定（プライマリソース）
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
    EUROSTAT_DATASET = "sts_inppd_m"

    # ECB Data API設定（フォールバック）
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    ECB_DATAFLOW = "STS"
    ECB_SERIES_KEY = "M.I9.N.PRIN.NS0020.4.000"

    def __init__(self):
        pass

    def get_ecb_ppi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """PPIデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "annual_rates": cached_data.get("annual_rates", {}),
                        "monthly_changes": cached_data.get("monthly_changes", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # Eurostat APIから取得（プライマリ）
        api_result = self._fetch_from_eurostat()
        data_source = "eurostat"

        # Eurostatが失敗した場合、ECB APIにフォールバック
        if not api_result:
            print("[ECBPPI] Eurostat failed, falling back to ECB API")
            api_result = self._fetch_from_ecb()
            data_source = "ecb_api"

        if api_result:
            next_release = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERNS[0],
                country=self.FMP_COUNTRY
            )

            cache_payload = {
                "annual_rates": api_result["annual_rates"],
                "monthly_changes": api_result["monthly_changes"],
                "metadata": {
                    "source": "Eurostat" if data_source == "eurostat" else "European Central Bank (ECB)",
                    "indicator": "PPI - Producer Price Index",
                    "data_start": "2015-01-01",
                    "description": "ユーロ圏生産者物価指数（PPI）",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "annual_rates": api_result["annual_rates"],
                "monthly_changes": api_result["monthly_changes"],
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": data_source,
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "annual_rates": file_cache.get("annual_rates", {}),
                "monthly_changes": file_cache.get("monthly_changes", {}),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "annual_rates": {},
            "monthly_changes": {},
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_eurostat(self, start_period: str = "2015-01") -> Optional[Dict[str, Any]]:
        """Eurostat APIからPPIデータを取得"""
        try:
            print("[ECBPPI] Fetching PPI data from Eurostat")

            url = f"{self.EUROSTAT_API_BASE}/{self.EUROSTAT_DATASET}"
            params = {
                "format": "JSON",
                "geo": "EA21",  # Euro area 21 countries (2026-01でEA20→EA21移行)
                "nace_r2": "B-E36",  # Total Industry (except construction)
                "s_adj": "NSA",  # Not seasonally adjusted
                "unit": "I21",  # Index 2021=100
                "sinceTimePeriod": start_period,
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            values = data.get("value", {})

            if not values:
                print("[ECBPPI] Eurostat returned no values")
                return None

            # 時間ディメンションを取得
            time_dim = data.get("dimension", {}).get("time", {}).get("category", {}).get("index", {})
            sorted_times = sorted(time_dim.items(), key=lambda x: x[1])

            # 指数データを構築
            ppi_index = []
            for period, idx in sorted_times:
                val = values.get(str(idx))
                if val is not None:
                    ppi_index.append({
                        "date": period,
                        "value": float(val)
                    })

            if not ppi_index:
                print("[ECBPPI] No valid Eurostat data points")
                return None

            # 前年比を計算
            ppi_annual = self._calculate_year_on_year_change(ppi_index)

            # 前月比を計算
            ppi_monthly = self._calculate_monthly_change(ppi_index)

            result = {
                "annual_rates": {
                    "ppi": ppi_annual or [],
                },
                "monthly_changes": {
                    "ppi": ppi_monthly or [],
                },
            }

            print(f"[ECBPPI] Eurostat: PPI YoY: {len(ppi_annual)}, PPI MoM: {len(ppi_monthly)}")
            if ppi_annual:
                print(f"[ECBPPI] Latest data: {ppi_annual[-1]}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECBPPI] Eurostat request error: {e}")
            return None
        except Exception as e:
            print(f"[ECBPPI] Eurostat parse error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_from_ecb(self, start_date: str = "2015-01-01") -> Optional[Dict[str, Any]]:
        """ECB APIからPPIデータを取得（フォールバック）"""
        try:
            print("[ECBPPI] Fetching PPI data from ECB API")

            url = f"{self.ECB_API_BASE}/{self.ECB_DATAFLOW}/{self.ECB_SERIES_KEY}"
            params = {
                "startPeriod": start_date,
                "format": "jsondata",
                "detail": "dataonly"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            ppi_index = []

            if "dataSets" in data and len(data["dataSets"]) > 0:
                dataset = data["dataSets"][0]

                if "series" in dataset:
                    dimensions = data.get("structure", {}).get("dimensions", {})
                    observation_dimension = dimensions.get("observation", [])

                    time_values = []
                    for dim in observation_dimension:
                        if dim.get("id") == "TIME_PERIOD":
                            time_values = [v.get("id") for v in dim.get("values", [])]
                            break

                    for series_data in dataset["series"].values():
                        observations = series_data.get("observations", {})

                        for obs_index, obs_value in observations.items():
                            time_index = int(obs_index)
                            if time_index < len(time_values):
                                date = time_values[time_index]
                                value = obs_value[0] if isinstance(obs_value, list) else obs_value

                                ppi_index.append({
                                    "date": date,
                                    "value": float(value) if value is not None else None
                                })

            ppi_index.sort(key=lambda x: x["date"])

            if not ppi_index:
                print("[ECBPPI] No valid ECB data points")
                return None

            # 前年比を計算
            ppi_annual = self._calculate_year_on_year_change(ppi_index)

            # 前月比を計算
            ppi_monthly = self._calculate_monthly_change(ppi_index)

            result = {
                "annual_rates": {
                    "ppi": ppi_annual or [],
                },
                "monthly_changes": {
                    "ppi": ppi_monthly or [],
                },
            }

            print(f"[ECBPPI] ECB: PPI YoY: {len(ppi_annual)}, PPI MoM: {len(ppi_monthly)}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECBPPI] ECB request error: {e}")
            return None
        except Exception as e:
            print(f"[ECBPPI] ECB parse error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_monthly_change(self, index_data: List[Dict]) -> List[Dict]:
        """指数データから前月比変化率を計算"""
        if not index_data or len(index_data) < 2:
            return []

        result = []
        for i in range(1, len(index_data)):
            current = index_data[i]
            previous = index_data[i - 1]

            if previous["value"] is not None and current["value"] is not None and previous["value"] != 0:
                monthly_change = ((current["value"] - previous["value"]) / previous["value"]) * 100
                result.append({
                    "date": current["date"],
                    "value": round(monthly_change, 2)
                })
            else:
                result.append({
                    "date": current["date"],
                    "value": None
                })

        return result

    def _calculate_year_on_year_change(self, index_data: List[Dict]) -> List[Dict]:
        """指数データから前年比変化率を計算"""
        if not index_data or len(index_data) < 13:
            return []

        result = []
        for i in range(12, len(index_data)):
            current = index_data[i]
            year_ago = index_data[i - 12]

            if year_ago["value"] is not None and current["value"] is not None and year_ago["value"] != 0:
                yoy_change = ((current["value"] - year_ago["value"]) / year_ago["value"]) * 100
                result.append({
                    "date": current["date"],
                    "value": round(yoy_change, 2)
                })
            else:
                result.append({
                    "date": current["date"],
                    "value": None
                })

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERNS[0],
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ECBPPI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ECBPPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ECB PPI",
            "source": "Eurostat (primary) / ECB API (fallback)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": {
                "ppi_yoy": len(cached_data.get("annual_rates", {}).get("ppi", [])) if cached_data else 0,
                "ppi_mom": len(cached_data.get("monthly_changes", {}).get("ppi", [])) if cached_data else 0,
            } if cached_data else {},
            "next_release": get_next_release_by_pattern(
                self.FMP_EVENT_PATTERNS[0],
                country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ecb_ppi_service = ECBPPIService()
