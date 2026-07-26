"""
ユーロ圏賃金・給与サービス
Eurostatから賃金・給与データを取得

指標:
- Wages and Salaries (D11) for Euro Area 20 (from 2023)
- 前年比 (YoY) 変化率

データソース:
- Eurostat API (lc_lci_r2_q dataset)
- Series Parameters:
  - freq: Q (Quarterly)
  - s_adj: CA (Calendar adjusted, not seasonally adjusted)
  - unit: PCH_SM (Percentage change compared to same period in previous year)
  - nace_r2: B-S (Industry, construction and services)
  - lcstruct: D11 (Wages and salaries total)
  - geo: EA20 (Euro area - 20 countries from 2023)

発表スケジュール:
- 3月・6月・9月・12月の13日〜21日（四半期ごと）
- 発表時刻: 18:00-18:10 CET

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


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eurostat_wages_cache.json"


class EurostatWagesService:
    """ユーロ圏賃金・給与サービス（Eurostat API）"""

    # Eurostat API base URL
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"

    # Dataset code
    DATASET = "lc_lci_r2_q"

    # Series parameters for EA20 Wages and Salaries YoY
    SERIES_PARAMS = {
        "freq": "Q",           # Quarterly
        "s_adj": "CA",         # Calendar adjusted, not seasonally adjusted
        "unit": "PCH_SM",      # Percentage change compared to same period in previous year
        "nace_r2": "B-S",      # Industry, construction and services
        "lcstruct": "D11",     # Wages and salaries (total)
        "geo": "EA21"          # Euro area - 21 countries (2026-01ブルガリア加盟でEA20→EA21)
    }

    DATA_CACHE_KEY = "eurozone:eurostat_wages:data"
    ECONALPHA_ID = "eu_wage_growth"  # DBマッピング（indicator_event_mapping）に合わせる

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """賃金・給与データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": file_cache.get("next_release"),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # Eurostat APIから取得
        wages_data = self._fetch_eurostat_data() or []

        if wages_data:
            latest = wages_data[-1] if wages_data else None
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "data": wages_data,
                "latest": latest,
                "metadata": {
                    "source": "Eurostat - Labour Cost Index",
                    "dataset": self.DATASET,
                    "area": "Euro area - 20 countries (from 2023)",
                    "unit": "Percentage change compared to same period in previous year",
                    "frequency": "Quarterly",
                    "adjustment": "Calendar adjusted, not seasonally adjusted",
                    "sector": "Industry, construction and services (B-S)",
                    "description": "Wages and salaries (total)",
                },
                "next_release": next_release,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": wages_data,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "eurostat_api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_eurostat_data(self, start_period: str = "2015-Q1") -> Optional[List[Dict]]:
        """
        Eurostat APIからデータを取得

        Args:
            start_period: 開始期間 (YYYY-QN)

        Returns:
            データポイントのリスト
        """
        # Build series key
        series_key = ".".join([
            self.SERIES_PARAMS["freq"],
            self.SERIES_PARAMS["s_adj"],
            self.SERIES_PARAMS["unit"],
            self.SERIES_PARAMS["nace_r2"],
            self.SERIES_PARAMS["lcstruct"],
            self.SERIES_PARAMS["geo"]
        ])

        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}/{series_key}/"

        params = {
            "format": "JSON",
            "startPeriod": start_period
        }

        try:
            print(f"[EurostatWages] Fetching from Eurostat API: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract dimensions and values
            dimensions = data.get("dimension", {})
            time_dim = dimensions.get("time", {})
            time_category = time_dim.get("category", {})
            time_index = time_category.get("index", {})

            values = data.get("value", {})

            if not time_index or not values:
                print("[EurostatWages] No data found in Eurostat response")
                return None

            # Create index to time mapping
            idx_to_time = {v: k for k, v in time_index.items()}

            # Build result list
            result = []
            for val_idx_str in sorted(values.keys(), key=lambda x: int(x)):
                val_idx = int(val_idx_str)
                time_period = idx_to_time.get(val_idx)
                value = values.get(val_idx_str)

                if time_period and value is not None:
                    result.append({
                        "date": time_period,
                        "value": float(value)
                    })

            print(f"[EurostatWages] Successfully fetched {len(result)} data points from Eurostat")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EurostatWages] API request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[EurostatWages] Data parsing error: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[EurostatWages] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EurostatWages] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Eurostat Wages and Salaries",
            "source": "Eurostat API (lc_lci_r2_q)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
eurostat_wages_service = EurostatWagesService()
