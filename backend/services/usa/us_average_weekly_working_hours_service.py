"""
平均週労働時間サービス
FRED APIからAWHAETP, AWHNONAG, AWHMANデータを取得

指標:
- AWHAETP: Average Weekly Hours of All Employees, Total Private（民間全体・全従業員）
- AWHNONAG: Average Weekly Hours of Production and Nonsupervisory Employees, Total Private（民間全体・生産労働者）
- AWHMAN: Average Weekly Hours of Production and Nonsupervisory Employees, Manufacturing（製造業・生産労働者）

データソース:
- FRED: https://fred.stlouisfed.org/series/AWHAETP
- FRED: https://fred.stlouisfed.org/series/AWHNONAG
- FRED: https://fred.stlouisfed.org/series/AWHMAN

発表スケジュール:
- BLS Employment Situation（雇用統計）
- 毎月第1金曜日 8:30 AM ET
- 失業率と同時発表

更新スケジュール: 月次（BLS雇用統計と同時）

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
AWHAETP_SERIES_ID = "AWHAETP"    # Average Weekly Hours of All Employees, Total Private（民間全体）
AWHMAN_SERIES_ID = "AWHMAN"      # Average Weekly Hours of Production and Nonsupervisory Employees, Manufacturing（製造業・生産労働者）
AWHNONAG_SERIES_ID = "AWHNONAG"  # Average Weekly Hours of Production and Nonsupervisory Employees, Total Private（民間全体・生産労働者）

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "us_average_weekly_working_hours_cache.json"


class UsAverageWeeklyWorkingHoursService:
    """平均週労働時間サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:us_average_weekly_working_hours:data"
    ECONALPHA_ID = "unemployment_rate"  # FMPマッピング用ID（失業率と同じスケジュール）

    SERIES_CONFIG = {
        "awhaetp": {
            "series_id": AWHAETP_SERIES_ID,
            "name": "民間全体（全従業員）",
            "color": "#1890ff",
        },
        "awhnonag": {
            "series_id": AWHNONAG_SERIES_ID,
            "name": "民間全体（生産労働者）",
            "color": "#52c41a",
        },
        "awhman": {
            "series_id": AWHMAN_SERIES_ID,
            "name": "製造業（生産労働者）",
            "color": "#fa8c16",
        },
    }

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_us_average_weekly_working_hours_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        平均週労働時間データを取得

        Returns:
            {
                "data": [{"date": str, "total_private": float, "manufacturing": float}, ...],
                "latest": {"date": str, "total_private": float, "manufacturing": float},
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
                        "series_config": self.SERIES_CONFIG,
                        "next_release": get_next_release_from_fmp('average_weekly_hours'),
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
                        "series_config": self.SERIES_CONFIG,
                        "next_release": get_next_release_from_fmp('average_weekly_hours'),
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
                "series_config": self.SERIES_CONFIG,
                "next_release": get_next_release_from_fmp('average_weekly_hours'),
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
                "series_config": self.SERIES_CONFIG,
                "next_release": get_next_release_from_fmp('average_weekly_hours'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "series_config": self.SERIES_CONFIG,
            "next_release": get_next_release_from_fmp('average_weekly_hours'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから平均週労働時間データを取得（3系列マージ）"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Average Weekly Working Hours from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 各系列を取得
            awhaetp_data = self._fetch_series(AWHAETP_SERIES_ID, start_date)
            awhnonag_data = self._fetch_series(AWHNONAG_SERIES_ID, start_date)
            awhman_data = self._fetch_series(AWHMAN_SERIES_ID, start_date)

            if not awhaetp_data and not awhnonag_data and not awhman_data:
                return None

            # 日付をキーにしてマージ
            awhaetp_map = {d["date"]: d["value"] for d in awhaetp_data}
            awhnonag_map = {d["date"]: d["value"] for d in awhnonag_data}
            awhman_map = {d["date"]: d["value"] for d in awhman_data}

            all_dates = sorted(set(
                list(awhaetp_map.keys()) +
                list(awhnonag_map.keys()) +
                list(awhman_map.keys())
            ))

            result = []
            for date in all_dates:
                item: Dict[str, Any] = {"date": date}
                v_awhaetp = awhaetp_map.get(date)
                v_awhnonag = awhnonag_map.get(date)
                v_awhman = awhman_map.get(date)
                if v_awhaetp is not None:
                    item["awhaetp"] = v_awhaetp
                if v_awhnonag is not None:
                    item["awhnonag"] = v_awhnonag
                if v_awhman is not None:
                    item["awhman"] = v_awhman
                # awhaetpがメイン系列なので、存在しない場合はスキップ
                if v_awhaetp is not None:
                    result.append(item)

            print(f"Fetched {len(result)} Average Weekly Working Hours records")
            return result

        except Exception as e:
            print(f"Error fetching Average Weekly Working Hours: {e}")
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
            "indicator": "Average Weekly Working Hours",
            "source": "FRED / BLS",
            "series_ids": [AWHAETP_SERIES_ID, AWHNONAG_SERIES_ID, AWHMAN_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
us_average_weekly_working_hours_service = UsAverageWeeklyWorkingHoursService()
