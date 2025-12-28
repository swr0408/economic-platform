"""
個人所得（Personal Income）サービス
FRED APIから名目PI・実質RPIデータを取得

指標:
- PI: Personal Income（名目個人所得）
- RPI: Real Personal Income（実質個人所得）

データソース:
- FRED: https://fred.stlouisfed.org/series/PI
- FRED: https://fred.stlouisfed.org/series/RPI
- BEA: https://www.bea.gov/data/income-saving/personal-income

発表スケジュール:
- BEA Personal Income and Outlays レポート
- 毎月末 8:30 AM ET
- BEAから次回発表日を自動取得

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import re
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.release_schedule_utils import PERSONAL_INCOME_CHECKER


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
PI_SERIES_ID = "PI"      # 名目個人所得（10億ドル、季節調整済み年率換算）
RPI_SERIES_ID = "RPI"    # 実質個人所得（2017年基準、10億ドル、季節調整済み年率換算）

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "personal_income_cache.json"


class PersonalIncomeService:
    """個人所得（Personal Income）サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:personal_income:data"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self.schedule_checker = PERSONAL_INCOME_CHECKER

    def get_personal_income_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        個人所得データを取得（名目・実質）

        Returns:
            {
                "nominal": {
                    "data": [{"date": str, "mom": float, "yoy": float}, ...],
                    "latest": {...}
                },
                "real": {
                    "data": [{"date": str, "mom": float, "yoy": float}, ...],
                    "latest": {...}
                },
                "next_release": None,
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
                        "nominal": cached_data.get("nominal"),
                        "real": cached_data.get("real"),
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
                        "nominal": file_cache.get("nominal"),
                        "real": file_cache.get("real"),
                        "next_release": None,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            cache_payload = {
                "nominal": api_data["nominal"],
                "real": api_data["real"],
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "nominal": api_data["nominal"],
                "real": api_data["real"],
                "next_release": None,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "nominal": file_cache.get("nominal"),
                "real": file_cache.get("real"),
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "nominal": None,
            "real": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """FRED APIから個人所得データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Personal Income from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 名目個人所得
            nominal_raw = self._fetch_series(PI_SERIES_ID, start_date)
            # 実質個人所得
            real_raw = self._fetch_series(RPI_SERIES_ID, start_date)

            if not nominal_raw or not real_raw:
                return None

            # 変化率を計算
            nominal_data = self._calculate_changes(nominal_raw)
            real_data = self._calculate_changes(real_raw)

            nominal_latest = nominal_data[-1] if nominal_data else None
            real_latest = real_data[-1] if real_data else None

            print(f"Fetched {len(nominal_data)} Personal Income records")
            return {
                "nominal": {
                    "data": nominal_data,
                    "latest": nominal_latest
                },
                "real": {
                    "data": real_data,
                    "latest": real_latest
                }
            }

        except Exception as e:
            print(f"Error fetching Personal Income: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_changes(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前月比・前年比を計算"""
        result = []
        for i, item in enumerate(raw_data):
            entry = {
                "date": item["date"],
                "mom": None,
                "yoy": None,
            }

            # 前月比（%）
            if i > 0:
                prev_value = raw_data[i - 1]["value"]
                if prev_value and prev_value != 0:
                    entry["mom"] = round((item["value"] / prev_value - 1) * 100, 2)

            # 前年比（%）
            if i >= 12:
                prev_year_value = raw_data[i - 12]["value"]
                if prev_year_value and prev_year_value != 0:
                    entry["yoy"] = round((item["value"] / prev_year_value - 1) * 100, 2)

            result.append(entry)
        return result

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
                        "value": value
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching FRED series {series_id}: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
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
            "indicator": "Personal Income",
            "source": "FRED / BEA",
            "series_ids": [PI_SERIES_ID, RPI_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "schedule_status": self.schedule_checker.get_status(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
personal_income_service = PersonalIncomeService()
