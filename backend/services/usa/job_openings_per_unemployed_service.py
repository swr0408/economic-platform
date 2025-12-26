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
- JOLTS: 毎月上旬（参照月の翌々月初旬）10:00 AM ET
- 失業率（UNEMPLOY）: 毎月第1金曜日 8:30 AM ET
- 両方の発表日のうち遅い方で更新判定

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
JOLTS_SERIES_ID = "JTSJOL"      # JOLTS求人件数（千人）
UNEMPLOY_SERIES_ID = "UNEMPLOY"  # 失業者数（千人）

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "job_openings_per_unemployed_cache.json"


class JobOpeningsPerUnemployedService:
    """求人倍率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:job_openings_per_unemployed:data"

    # 発表時刻設定（ET）
    # JOLTS: 10:00 AM ET, Employment Situation: 8:30 AM ET
    # 両方の発表日のうち遅い方で判定するため、両方の発表日時を取得する必要がある

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

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
                "next_release": {
                    "jolts": {"date": str, "label": str} | null,
                    "empsit": {"date": str, "label": str} | null
                },
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
                    next_release = self._get_next_release()
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
                    next_release = self._get_next_release()
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
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
        next_release = self._get_next_release()

        if api_data:
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }

            # キャッシュに保存
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
            "next_release": next_release,
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
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - JOLTSまたはEmployment Situationの発表日時を過ぎており、
          かつ最終更新がその発表日時より前なら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 両方の発表日時を取得
            next_release = self._get_next_release()

            # JOLTS発表日時をチェック
            jolts_release = next_release.get("jolts")
            if jolts_release and jolts_release.get("date"):
                release_date_str = jolts_release["date"]
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

                # JOLTS発表時刻（10:00 ET）をJSTに変換
                release_et = datetime(
                    release_date.year, release_date.month, release_date.day,
                    10, 0, tzinfo=ET
                )
                release_jst = release_et.astimezone(JST)

                if now >= release_jst and last_updated < release_jst:
                    return True

            # Employment Situation発表日時をチェック
            empsit_release = next_release.get("empsit")
            if empsit_release and empsit_release.get("date"):
                release_date_str = empsit_release["date"]
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

                # Employment Situation発表時刻（8:30 ET）をJSTに変換
                release_et = datetime(
                    release_date.year, release_date.month, release_date.day,
                    8, 30, tzinfo=ET
                )
                release_jst = release_et.astimezone(JST)

                if now >= release_jst and last_updated < release_jst:
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self) -> Dict[str, Any]:
        """
        次回発表日を取得

        JOLTSとEmployment Situationの両方の発表日を返す
        """
        result = {
            "jolts": None,
            "empsit": None
        }

        try:
            # JOLTSの発表日（jolts_indeed_serviceから取得）
            from services.usa.jolts_indeed_service import jolts_indeed_service
            jolts_next = jolts_indeed_service._get_next_release()
            if jolts_next:
                result["jolts"] = jolts_next
        except Exception as e:
            print(f"Error getting JOLTS next release: {e}")

        try:
            # Employment Situationの発表日（unemployment_rate_serviceから取得）
            from services.usa.unemployment_rate_service import unemployment_rate_service
            empsit_next = unemployment_rate_service._get_next_release()
            if empsit_next:
                result["empsit"] = empsit_next
        except Exception as e:
            print(f"Error getting Employment Situation next release: {e}")

        return result

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
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
job_openings_per_unemployed_service = JobOpeningsPerUnemployedService()
