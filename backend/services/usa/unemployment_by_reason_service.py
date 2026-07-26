"""
失業率内訳（Unemployment by Reason）サービス
FRED APIから失業者の内訳データを取得

指標:
- LNS13023653: レイオフ（Unemployment Level - Job Losers On Layoff）
- LNS13025699: レイオフ以外の失業者
- LNS13023705: 自発的離職者（Job Leavers）
- LNS13023557: 再参入者（Reentrants）
- LNS13023569: 新規参入者（New Entrants）

データソース:
- FRED: https://fred.stlouisfed.org/

発表スケジュール:
- BLS Employment Situation（雇用統計）と同時
- 毎月第1金曜日 8:30 AM ET
- 失業率サービスと発表スケジュールを共有

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
    resolve_last_updated_after_fetch,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
SERIES_CONFIG = {
    "layoff": {
        "series_id": "LNS13023653",
        "name": "レイオフ",
        "name_en": "Job Losers On Layoff",
        "color": "#ff4d4f"
    },
    "other_losers": {
        "series_id": "LNS13025699",
        "name": "レイオフ以外",
        "name_en": "Other Job Losers",
        "color": "#fa8c16"
    },
    "leavers": {
        "series_id": "LNS13023705",
        "name": "自発的離職者",
        "name_en": "Job Leavers",
        "color": "#52c41a"
    },
    "reentrants": {
        "series_id": "LNS13023557",
        "name": "再参入者",
        "name_en": "Reentrants",
        "color": "#1890ff"
    },
    "new_entrants": {
        "series_id": "LNS13023569",
        "name": "新規参入者",
        "name_en": "New Entrants",
        "color": "#722ed1"
    }
}

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "unemployment_by_reason_cache.json"


class UnemploymentByReasonService:
    """失業率内訳サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:unemployment_by_reason:data"
    ECONALPHA_ID = "unemployment_rate"  # FMPマッピング用ID（失業率と同じスケジュール）

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_unemployment_by_reason_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        失業率内訳データを取得

        Returns:
            {
                "data": [{"date": str, "layoff": float, "other_losers": float, ...}, ...],
                "latest": {...},
                "series_config": {...},
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
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "series_config": SERIES_CONFIG,
                        "next_release": None,
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
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "series_config": SERIES_CONFIG,
                        "next_release": None,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None

            # 発表時刻レース対策: ソース未反映の旧月を発表後タイムスタンプで保存すると
            # should_refresh が消化済み判定し次回発表まで凍結するため、ラグガードで決定する
            prev_cache = redis_client.get(self.DATA_CACHE_KEY) or self._load_file_cache() or {}
            prev_latest = prev_cache.get("latest") or {}
            resolved_last_updated = resolve_last_updated_after_fetch(
                self.ECONALPHA_ID,
                latest.get("date") if isinstance(latest, dict) else None,
                prev_latest.get("date") if isinstance(prev_latest, dict) else None,
                prev_cache.get("last_updated"),
            )

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": resolved_last_updated
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "series_config": SERIES_CONFIG,
                "next_release": None,
                "cached": False,
                "source": "api",
                "last_updated": resolved_last_updated
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "series_config": SERIES_CONFIG,
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "series_config": SERIES_CONFIG,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから失業率内訳データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Unemployment by Reason from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 各シリーズのデータを取得
            all_series_data = {}
            for key, config in SERIES_CONFIG.items():
                series_data = self._fetch_series(config["series_id"], start_date)
                all_series_data[key] = {item["date"]: item["value"] for item in series_data}

            # データをマージ（日付ベース）
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

            print(f"Fetched {len(merged_data)} Unemployment by Reason records")
            return merged_data

        except Exception as e:
            print(f"Error fetching Unemployment by Reason: {e}")
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
            "indicator": "Unemployment by Reason",
            "source": "FRED / BLS",
            "series_ids": [config["series_id"] for config in SERIES_CONFIG.values()],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
unemployment_by_reason_service = UnemploymentByReasonService()
