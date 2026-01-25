"""
JOLTS求人 / Indeed求人件数サービス
FRED APIからデータを取得

指標:
- JTSJOL: JOLTS Job Openings（JOLTS求人件数、千人）
- IHLIDXUS: Indeed Job Postings Index（Indeed求人件数指数）

データソース:
- FRED: https://fred.stlouisfed.org/series/JTSJOL
- FRED: https://fred.stlouisfed.org/series/IHLIDXUS

発表スケジュール:
- JOLTS: 毎月上旬（参照月の翌々月初旬）
- 発表期間: 毎月29日〜翌月13日（月跨ぎ）
- 発表時刻: 23:00 (夏) / 0:00 (冬) JST
- Indeed: 日次更新

キャッシュ方式: 発表期間ベース判定方式
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
ET = ZoneInfo("America/New_York")

# FREDシリーズID
JOLTS_SERIES_ID = "JTSJOL"       # JOLTS求人件数（千人）
INDEED_SERIES_ID = "IHLIDXUS"   # Indeed求人件数指数

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "jolts_indeed_cache.json"

# 系列設定
SERIES_CONFIG = {
    "jolts": {
        "series_id": JOLTS_SERIES_ID,
        "name": "JOLTS求人件数",
        "name_en": "JOLTS Job Openings",
        "color": "#1890ff"  # 青
    },
    "indeed": {
        "series_id": INDEED_SERIES_ID,
        "name": "Indeed求人件数指数",
        "name_en": "Indeed Job Postings Index",
        "color": "#ff4d4f"  # 赤
    }
}


class JoltsIndeedService:
    """JOLTS求人 / Indeed求人件数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:jolts_indeed:data"
    ECONALPHA_ID = "jolts_openings"  # FMPマッピング用ID

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_jolts_indeed_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        JOLTS / Indeed求人データを取得

        Returns:
            {
                "data": [{"date": str, "jolts": float, "indeed": float}, ...],
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
                        "next_release": get_next_release_from_fmp('jolts_openings'),
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
                        "next_release": get_next_release_from_fmp('jolts_openings'),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = self._get_latest_values(api_data)

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
                "next_release": get_next_release_from_fmp('jolts_openings'),
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
                "next_release": get_next_release_from_fmp('jolts_openings'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "series_config": SERIES_CONFIG,
            "next_release": get_next_release_from_fmp('jolts_openings'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _get_latest_values(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """JOLTSとIndeedそれぞれの最新値を取得"""
        latest = {
            "date": None,
            "jolts": None,
            "jolts_date": None,
            "indeed": None,
            "indeed_date": None
        }

        # 逆順で最新値を探す
        for item in reversed(data):
            if latest["jolts"] is None and item.get("jolts") is not None:
                latest["jolts"] = item["jolts"]
                latest["jolts_date"] = item["date"]
            if latest["indeed"] is None and item.get("indeed") is not None:
                latest["indeed"] = item["indeed"]
                latest["indeed_date"] = item["date"]
            if latest["jolts"] is not None and latest["indeed"] is not None:
                break

        # 全体の日付は最新のものを使用
        if data:
            latest["date"] = data[-1]["date"]

        return latest

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIからデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching JOLTS / Indeed data from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # JOLTS求人件数
            jolts_raw = self._fetch_series(JOLTS_SERIES_ID, start_date)
            # Indeed求人件数指数
            indeed_raw = self._fetch_series(INDEED_SERIES_ID, start_date)

            if not jolts_raw and not indeed_raw:
                return None

            # データをマージ
            merged_data = self._merge_data(jolts_raw, indeed_raw)

            print(f"Fetched {len(merged_data)} JOLTS / Indeed records")
            return merged_data

        except Exception as e:
            print(f"Error fetching JOLTS / Indeed data: {e}")
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
        jolts_data: List[Dict[str, Any]],
        indeed_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """JOLTSとIndeedのデータをマージ"""
        # 日付でインデックス化
        jolts_map = {item["date"]: item["value"] for item in jolts_data}
        indeed_map = {item["date"]: item["value"] for item in indeed_data}

        # 全日付を収集
        all_dates = sorted(set(list(jolts_map.keys()) + list(indeed_map.keys())))

        result = []
        for d in all_dates:
            entry = {
                "date": d,
                "jolts": jolts_map.get(d),
                "indeed": indeed_map.get(d)
            }
            # 少なくとも1つの値がある場合のみ追加
            if entry["jolts"] is not None or entry["indeed"] is not None:
                result.append(entry)

        return result

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
            "indicator": "JOLTS / Indeed Job Postings",
            "source": "FRED / BLS",
            "series_ids": [JOLTS_SERIES_ID, INDEED_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
jolts_indeed_service = JoltsIndeedService()
