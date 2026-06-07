"""
出生地別労働者数サービス
FRED APIから出生地別の労働力人口・雇用者数データを取得

指標:
- LNU01073395: 労働力人口（国内生まれ） - Civilian Labor Force, Native Born
- LNU01073413: 労働力人口（海外生まれ） - Civilian Labor Force, Foreign Born
- LNU02073395: 雇用者数（国内生まれ）   - Employment Level, Native Born
- LNU02073413: 雇用者数（海外生まれ）   - Employment Level, Foreign Born

データソース:
- FRED: https://fred.stlouisfed.org/
- BLS: https://www.bls.gov/news.release/empsit.toc.htm

発表スケジュール:
- BLS Employment Situation（雇用統計）と同時
- 毎月第1金曜日 8:30 AM ET
- 非農業部門雇用者数（NFP）と発表スケジュールを共有

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FREDシリーズID
SERIES_CONFIG = {
    "labor_force_native": {
        "series_id": "LNU01073395",
        "name": "労働力人口（国内生まれ）",
        "name_en": "Civilian Labor Force - Native Born",
        "color": "#1890ff"
    },
    "labor_force_foreign": {
        "series_id": "LNU01073413",
        "name": "労働力人口（海外生まれ）",
        "name_en": "Civilian Labor Force - Foreign Born",
        "color": "#fa8c16"
    },
    "employment_native": {
        "series_id": "LNU02073395",
        "name": "雇用者数（国内生まれ）",
        "name_en": "Employment Level - Native Born",
        "color": "#52c41a"
    },
    "employment_foreign": {
        "series_id": "LNU02073413",
        "name": "雇用者数（海外生まれ）",
        "name_en": "Employment Level - Foreign Born",
        "color": "#eb2f96"
    }
}

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "number_of_workers_by_place_of_birth_cache.json"


class NumberOfWorkersByPlaceOfBirthService:
    """出生地別労働者数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:number_of_workers_by_place_of_birth:data"
    ECONALPHA_ID = "nonfarm_payrolls"  # NFPと同タイミングで発表

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_number_of_workers_by_place_of_birth_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        出生地別労働者数データを取得

        Returns:
            {
                "data": [{"date": str, "labor_force_native": float, "labor_force_foreign": float,
                          "employment_native": float, "employment_foreign": float}, ...],
                "latest": {...},
                "series_config": {...},
                "next_release": {"date": str, "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "series_config": SERIES_CONFIG,
                        "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "series_config": SERIES_CONFIG,
                        "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "series_config": SERIES_CONFIG,
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "series_config": SERIES_CONFIG,
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "series_config": SERIES_CONFIG,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから出生地別労働者数データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Number of Workers by Place of Birth from FRED...")

            if not start_date:
                start_date = "2007-01-01"

            all_series_data = {}
            for key, config in SERIES_CONFIG.items():
                series_data = self._fetch_series(config["series_id"], start_date)
                all_series_data[key] = {item["date"]: item["value"] for item in series_data}

            all_dates = set()
            for series_data in all_series_data.values():
                all_dates.update(series_data.keys())

            sorted_dates = sorted(all_dates)
            merged_data = []

            for date_str in sorted_dates:
                entry = {"date": date_str}
                has_data = False
                for key in SERIES_CONFIG.keys():
                    value = all_series_data[key].get(date_str)
                    entry[key] = value
                    if value is not None:
                        has_data = True
                if has_data:
                    merged_data.append(entry)

            print(f"Fetched {len(merged_data)} Workers by Place of Birth records")
            return merged_data

        except Exception as e:
            print(f"Error fetching Workers by Place of Birth: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_series(self, series_id: str, start_date: str) -> List[Dict[str, Any]]:
        """FRED APIからシリーズデータを取得"""
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            observations = data.get("observations", [])

            result = []
            for obs in observations:
                try:
                    value_str = obs.get("value", "")
                    if value_str == "." or not value_str:
                        continue
                    value = float(value_str)
                    result.append({
                        "date": obs["date"],
                        "value": round(value, 0)  # 千人単位
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching FRED series {series_id}: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

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
            "indicator": "Number of Workers by Place of Birth",
            "source": "FRED / BLS",
            "series_ids": [config["series_id"] for config in SERIES_CONFIG.values()],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
number_of_workers_by_place_of_birth_service = NumberOfWorkersByPlaceOfBirthService()
