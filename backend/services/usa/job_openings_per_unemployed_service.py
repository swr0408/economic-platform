"""
求人倍率（Job Openings per Unemployed）サービス
FRED APIから求人件数と失業者数を取得し、比率を計算

指標:
- JTSJOL: JOLTS求人件数（Job Openings: Total Nonfarm、千人）
- UNEMPLOY: 失業者数（Unemployment Level、千人）
- 求人倍率 = JTSJOL / UNEMPLOY

データソース:
- FRED: https://fred.stlouisfed.org/series/JTSJOL
- FRED: https://fred.stlouisfed.org/series/UNEMPLOY

発表スケジュール:
- JOLTS: 毎月29日〜翌月13日、23:00 (夏) / 0:00 (冬) JST
- 失業率（UNEMPLOY）: 毎月1〜15日、21:30 (夏) / 22:30 (冬) JST
- 両方のスケジュールで判定

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
from services.usa.release_schedule_utils import (
    JOLTS_OPENINGS_CHECKER,
    UNEMPLOYMENT_RATE_CHECKER,
)
from services.usa.fmp_next_release_utils import resolve_last_updated_after_fetch


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
JOLTS_SERIES_ID = "JTSJOL"      # JOLTS求人件数（千人）
UNEMPLOY_SERIES_ID = "UNEMPLOY"  # 失業者数（千人）

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "job_openings_per_unemployed_cache.json"


class JobOpeningsPerUnemployedService:
    """求人倍率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:job_openings_per_unemployed:data"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self.jolts_checker = JOLTS_OPENINGS_CHECKER
        self.unemployment_checker = UNEMPLOYMENT_RATE_CHECKER

    def get_job_openings_per_unemployed_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        求人倍率データを取得

        Returns:
            {
                "data": [{"date": str, "value": float, "jolts": float, "unemployed": float}, ...],
                "latest": {...},
                "next_release": null,
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
            # (分母の失業者数は雇用統計と同時更新のため unemployment_rate スケジュールで判定)
            prev_cache = redis_client.get(self.DATA_CACHE_KEY) or self._load_file_cache() or {}
            prev_latest = prev_cache.get("latest") or {}
            resolved_last_updated = resolve_last_updated_after_fetch(
                "unemployment_rate",
                latest.get("date") if isinstance(latest, dict) else None,
                prev_latest.get("date") if isinstance(prev_latest, dict) else None,
                prev_cache.get("last_updated"),
            )

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": resolved_last_updated
            }

            # キャッシュに保存
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
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
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """FRED APIから求人件数・失業者数データを取得し、比率を計算"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching Job Openings per Unemployed from FRED API...")

            start = start_date or "2000-01-01"

            # 求人件数を取得
            jolts_data = self._fetch_series(JOLTS_SERIES_ID, start)
            # 失業者数を取得
            unemploy_data = self._fetch_series(UNEMPLOY_SERIES_ID, start)

            if not jolts_data or not unemploy_data:
                print("No data fetched from FRED")
                return []

            # 比率を計算
            result = self._calculate_ratio(jolts_data, unemploy_data)

            print(f"Fetched {len(result)} Job Openings per Unemployed records")
            return result

        except Exception as e:
            print(f"Error fetching Job Openings per Unemployed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_series(self, series_id: str, start_date: str) -> Dict[str, float]:
        """FREDシリーズを取得"""
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

            result = {}
            for obs in data.get("observations", []):
                date_str = obs.get("date")
                value = obs.get("value")

                if date_str and value and value != ".":
                    try:
                        result[date_str] = float(value)
                    except (ValueError, TypeError):
                        continue

            print(f"Fetched {len(result)} records for {series_id}")
            return result

        except Exception as e:
            print(f"Error fetching {series_id}: {e}")
            return {}

    def _calculate_ratio(
        self,
        jolts_data: Dict[str, float],
        unemploy_data: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """求人倍率を計算（JOLTS / UNEMPLOY）"""
        # 共通の日付を取得
        common_dates = sorted(set(jolts_data.keys()) & set(unemploy_data.keys()))

        result = []
        for date_str in common_dates:
            jolts = jolts_data.get(date_str)
            unemploy = unemploy_data.get(date_str)

            if jolts is not None and unemploy is not None and unemploy > 0:
                ratio = round(jolts / unemploy, 2)
                result.append({
                    "date": date_str,
                    "value": ratio,
                    "jolts": jolts,
                    "unemployed": unemploy
                })

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（発表期間ベース）

        JOLTSまたは失業率のいずれかの発表期間内であれば更新チェック
        """
        # いずれかのスケジュールで更新が必要なら更新
        return (
            self.jolts_checker.should_refresh(last_updated_str) or
            self.unemployment_checker.should_refresh(last_updated_str)
        )

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
            "indicator": "Job Openings per Unemployed",
            "series_ids": [JOLTS_SERIES_ID, UNEMPLOY_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "schedule_status": {
                "jolts": self.jolts_checker.get_status(),
                "unemployment": self.unemployment_checker.get_status()
            },
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
job_openings_per_unemployed_service = JobOpeningsPerUnemployedService()
