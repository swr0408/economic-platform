"""
ADP雇用者数（ADP National Employment Report）サービス
FRED APIからADP雇用者数データを取得

指標:
- ADPMNUSNERSA: ADP National Employment Report, All Employees, Total Nonfarm, Monthly, Seasonally Adjusted

データソース:
- FRED: https://fred.stlouisfed.org/series/ADPMNUSNERSA
- ADP公式: https://adpemploymentreport.com/

発表スケジュール:
- 毎月第1水曜日 8:15 AM ET（雇用統計の2日前）
- 発表スケジュールはADP公式ページからスクレイピング（半年に1回更新）

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
from bs4 import BeautifulSoup

from core.redis_client import redis_client
from services.usa.release_schedule_utils import ADP_EMPLOYMENT_CHECKER


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
SERIES_ID = "ADPMNUSNERSA"

# ADP公式カレンダーURL
ADP_CALENDAR_URL = "https://adpemploymentreport.com/"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "adp_employment_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "adp_schedule.json"


class ADPEmploymentService:
    """ADP雇用者数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:adp_employment:data"
    SCHEDULE_CACHE_KEY = "adp:schedule"

    # 発表時刻設定（ET）- 8:15 AM ET
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 15

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self.schedule_checker = ADP_EMPLOYMENT_CHECKER

    def get_adp_employment_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ADP雇用者数データを取得

        Returns:
            {
                "data": [{"date": str, "value": float, "mom": float, "yoy": float}, ...],
                "latest": {...},
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
            # 前月比・前年比を計算
            processed_data = self._calculate_changes(api_data)
            latest = processed_data[-1] if processed_data else None

            cache_payload = {
                "data": processed_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": processed_data,
                "latest": latest,
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

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIからADP雇用者数データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching ADP Employment from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": SERIES_ID,
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

            print(f"Fetched {len(result)} ADP Employment records")
            return result

        except Exception as e:
            print(f"Error fetching ADP Employment: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前月比・前年比を計算"""
        result = []
        data_by_date = {d["date"]: d["value"] for d in data}

        for item in data:
            current_date = datetime.strptime(item["date"], "%Y-%m-%d")
            current_value = item["value"]

            # 前月の日付を計算
            if current_date.month == 1:
                prev_month_date = current_date.replace(year=current_date.year - 1, month=12, day=1)
            else:
                prev_month_date = current_date.replace(month=current_date.month - 1, day=1)
            prev_month_str = prev_month_date.strftime("%Y-%m-%d")

            # 前年同月の日付を計算
            prev_year_date = current_date.replace(year=current_date.year - 1)
            prev_year_str = prev_year_date.strftime("%Y-%m-%d")

            # 前月比（千人単位の増減）
            prev_month_value = data_by_date.get(prev_month_str)
            mom = None
            if prev_month_value is not None and current_value is not None:
                mom = round(current_value - prev_month_value, 0)

            # 前年比（%）
            prev_year_value = data_by_date.get(prev_year_str)
            yoy = None
            if prev_year_value is not None and prev_year_value != 0 and current_value is not None:
                yoy = round((current_value - prev_year_value) / prev_year_value * 100, 2)

            result.append({
                "date": item["date"],
                "value": current_value,
                "mom": mom,  # 前月比（千人）
                "yoy": yoy   # 前年比（%）
            })

        return result

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
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ADP National Employment Report",
            "source": "FRED / ADP",
            "series_id": SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "schedule_status": self.schedule_checker.get_status(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
adp_employment_service = ADPEmploymentService()
