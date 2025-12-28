"""
複数の仕事を持つ人 / 経済的理由によるパートタイムサービス
FRED APIからデータを取得

指標:
- LNS12026619: Multiple Jobholders（複数の仕事を持つ人、千人）
- LNS12032194: Part-Time for Economic Reasons（経済的理由によるパートタイム、千人）

データソース:
- FRED: https://fred.stlouisfed.org/series/LNS12026619
- FRED: https://fred.stlouisfed.org/series/LNS12032194
- BLS: https://www.bls.gov/schedule/news_release/empsit.htm

発表スケジュール:
- BLS Employment Situation（雇用統計）
- 毎月第1金曜日 8:30 AM ET
- 失業率と同じ発表タイミング

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
from services.usa.release_schedule_utils import UNEMPLOYMENT_RATE_CHECKER


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
MULTIPLE_JOBS_SERIES_ID = "LNS12026619"   # 複数の仕事を持つ人（千人）
PARTTIME_ECON_SERIES_ID = "LNS12032194"   # 経済的理由によるパートタイム（千人）

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "multiple_jobs_parttime_cache.json"

# 系列設定
SERIES_CONFIG = {
    "multiple_jobs": {
        "series_id": MULTIPLE_JOBS_SERIES_ID,
        "name": "複数の仕事を持つ人",
        "name_en": "Multiple Jobholders",
        "color": "#1890ff"  # 青
    },
    "parttime_econ": {
        "series_id": PARTTIME_ECON_SERIES_ID,
        "name": "経済的理由によるパートタイム",
        "name_en": "Part-Time for Economic Reasons",
        "color": "#fa8c16"  # オレンジ
    }
}


class MultipleJobsPartTimeService:
    """複数の仕事を持つ人 / 経済的理由によるパートタイムサービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:multiple_jobs_parttime:data"

    # 発表時刻設定（ET）- 8:30 AM ET（失業率と同じ）
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self.schedule_checker = UNEMPLOYMENT_RATE_CHECKER

    def get_multiple_jobs_parttime_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        複数の仕事を持つ人 / 経済的理由によるパートタイムデータを取得

        Returns:
            {
                "data": [{"date": str, "multiple_jobs": float, "parttime_econ": float}, ...],
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
                "next_release": None,
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
        """FRED APIからデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Multiple Jobs / Part-Time for Economic Reasons from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 複数の仕事を持つ人
            multiple_jobs_raw = self._fetch_series(MULTIPLE_JOBS_SERIES_ID, start_date)
            # 経済的理由によるパートタイム
            parttime_econ_raw = self._fetch_series(PARTTIME_ECON_SERIES_ID, start_date)

            if not multiple_jobs_raw and not parttime_econ_raw:
                return None

            # データをマージ
            merged_data = self._merge_data(multiple_jobs_raw, parttime_econ_raw)

            print(f"Fetched {len(merged_data)} Multiple Jobs / Part-Time records")
            return merged_data

        except Exception as e:
            print(f"Error fetching Multiple Jobs / Part-Time data: {e}")
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
                        "value": round(value, 0)  # 千人単位、整数
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching FRED series {series_id}: {e}")
            return []

    def _merge_data(
        self,
        multiple_jobs_data: List[Dict[str, Any]],
        parttime_econ_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """複数の仕事を持つ人と経済的理由によるパートタイムのデータをマージ"""
        # 日付でインデックス化
        multiple_jobs_map = {item["date"]: item["value"] for item in multiple_jobs_data}
        parttime_econ_map = {item["date"]: item["value"] for item in parttime_econ_data}

        # 全日付を収集
        all_dates = sorted(set(list(multiple_jobs_map.keys()) + list(parttime_econ_map.keys())))

        result = []
        for date in all_dates:
            entry = {
                "date": date,
                "multiple_jobs": multiple_jobs_map.get(date),
                "parttime_econ": parttime_econ_map.get(date)
            }
            # 少なくとも1つの値がある場合のみ追加
            if entry["multiple_jobs"] is not None or entry["parttime_econ"] is not None:
                result.append(entry)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（失業率と同じ発表タイミング）"""
        return self.schedule_checker.should_refresh(last_updated_str)

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
            "indicator": "Multiple Jobs / Part-Time for Economic Reasons",
            "source": "FRED / BLS",
            "series_ids": [MULTIPLE_JOBS_SERIES_ID, PARTTIME_ECON_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "schedule_status": self.schedule_checker.get_status(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
multiple_jobs_parttime_service = MultipleJobsPartTimeService()
