"""
失業率 / 広義の失業率サービス
FRED APIからUNRATE & U6RATEデータを取得

指標:
- UNRATE: Unemployment Rate（失業率）
- U6RATE: Total Unemployed Plus All Persons Marginally Attached to the Labor Force Plus Total Employed Part Time for Economic Reasons（広義の失業率）

データソース:
- FRED: https://fred.stlouisfed.org/series/UNRATE
- FRED: https://fred.stlouisfed.org/series/U6RATE

発表スケジュール:
- BLS Employment Situation（雇用統計）
- 毎月第1金曜日 8:30 AM ET
- 発表時刻: 21:30 (夏) / 22:30 (冬) JST

キャッシュ方式: FMP 3分方式（発表時刻から3分間は毎分更新チェック）
"""
import os
import json
from datetime import datetime, date
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
ET = ZoneInfo("America/New_York")

# FREDシリーズID
UNRATE_SERIES_ID = "UNRATE"     # 失業率
U6RATE_SERIES_ID = "U6RATE"     # 広義の失業率（U-6）

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "unemployment_rate_cache.json"


class UnemploymentRateService:
    """失業率 / 広義の失業率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:unemployment_rate:data"
    ECONALPHA_ID = "unemployment_rate"  # FMPマッピング用ID

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_unemployment_rate_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        失業率データを取得（失業率 + 広義の失業率）

        Returns:
            {
                "data": [{"date": str, "unrate": float, "u6rate": float}, ...],
                "latest": {...},
                "next_release": {"date": str, "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_from_fmp('unemployment_rate')
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    next_release = get_next_release_from_fmp('unemployment_rate')
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None
            next_release = get_next_release_from_fmp('unemployment_rate')

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
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_from_fmp('unemployment_rate')
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('unemployment_rate'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから失業率データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Unemployment Rate from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 失業率（UNRATE）
            unrate_raw = self._fetch_series(UNRATE_SERIES_ID, start_date)
            # 広義の失業率（U6RATE）
            u6rate_raw = self._fetch_series(U6RATE_SERIES_ID, start_date)

            if not unrate_raw:
                return None

            # データをマージ
            merged_data = self._merge_data(unrate_raw, u6rate_raw)

            print(f"Fetched {len(merged_data)} Unemployment Rate records")
            return merged_data

        except Exception as e:
            print(f"Error fetching Unemployment Rate: {e}")
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
                        "value": round(value, 1)
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching FRED series {series_id}: {e}")
            return []

    def _merge_data(
        self,
        unrate_data: List[Dict[str, Any]],
        u6rate_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """UNRATE と U6RATE データをマージ"""
        # U6RATEを日付でインデックス化
        u6rate_map = {item["date"]: item["value"] for item in u6rate_data}

        result = []
        for item in unrate_data:
            entry = {
                "date": item["date"],
                "unrate": item["value"],
                "u6rate": u6rate_map.get(item["date"])
            }
            result.append(entry)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（FMP 3分方式）

        FMPのイベントスケジュールに基づいて、発表時刻から3分間は
        毎分更新チェックを行い、新しいデータを取得する。
        """
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
        next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

        return {
            "indicator": "Unemployment Rate",
            "source": "FRED / BLS",
            "series_ids": [UNRATE_SERIES_ID, U6RATE_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
unemployment_rate_service = UnemploymentRateService()
