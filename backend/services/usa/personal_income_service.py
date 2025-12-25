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
from bs4 import BeautifulSoup

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
PI_SERIES_ID = "PI"      # 名目個人所得（10億ドル、季節調整済み年率換算）
RPI_SERIES_ID = "RPI"    # 実質個人所得（2017年基準、10億ドル、季節調整済み年率換算）

# BEA リリーススケジュールURL
BEA_PERSONAL_INCOME_URL = "https://www.bea.gov/data/income-saving/personal-income"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "personal_income_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "bea_personal_income_schedule.json"

# 月名マッピング
MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9,
    'oct': 10, 'nov': 11, 'dec': 12
}


class PersonalIncomeService:
    """個人所得（Personal Income）サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:personal_income:data"
    SCHEDULE_CACHE_KEY = "bea:personal_income:schedule"

    # 発表時刻設定（ET）- 8:30 AM ET
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

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
                    next_release = self._get_next_release()
                    return {
                        "nominal": cached_data.get("nominal"),
                        "real": cached_data.get("real"),
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
                        "nominal": file_cache.get("nominal"),
                        "real": file_cache.get("real"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)
        next_release = self._get_next_release()

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
                "next_release": next_release,
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
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "nominal": None,
            "real": None,
            "next_release": next_release,
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
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            next_release = self._get_next_release()

            if next_release and next_release.get("date"):
                release_date_str = next_release["date"]
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

                release_et = datetime(
                    release_date.year, release_date.month, release_date.day,
                    self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                    tzinfo=ET
                )
                release_jst = release_et.astimezone(JST)

                if now >= release_jst and last_updated < release_jst:
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（BEAからスクレイピング）"""
        try:
            # キャッシュチェック
            cached_release = self._get_cached_schedule()
            if cached_release:
                release_date = datetime.strptime(cached_release["date"], "%Y-%m-%d").date()
                if release_date >= date.today():
                    return cached_release

            # BEAページからスクレイピング
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            response = requests.get(BEA_PERSONAL_INCOME_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()

            pattern = r'Next\s+release[:\s]+(\w+)\s+(\d{1,2}),?\s*(\d{4})'
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                month_name = match.group(1).lower()
                day = int(match.group(2))
                year = int(match.group(3))

                month_num = MONTH_MAP.get(month_name)
                if month_num:
                    release_date = date(year, month_num, day)
                    result = {
                        "date": release_date.strftime("%Y-%m-%d"),
                        "label": f"Personal Income - {release_date.strftime('%Y/%m/%d')} 8:30 ET"
                    }
                    self._save_schedule_cache(result)
                    return result

            return self._calculate_next_release_fallback()

        except Exception as e:
            print(f"Error getting next release: {e}")
            return self._calculate_next_release_fallback()

    def _calculate_next_release_fallback(self) -> Optional[Dict[str, Any]]:
        """次回発表日のフォールバック計算"""
        try:
            now = datetime.now(ET)
            today = now.date()

            if today.month == 12:
                next_month = date(today.year + 1, 1, 1)
            else:
                next_month = date(today.year, today.month + 1, 1)

            last_day_of_month = next_month - timedelta(days=1)
            release_date = last_day_of_month
            while release_date.weekday() >= 5:
                release_date -= timedelta(days=1)

            release_et = datetime(
                release_date.year, release_date.month, release_date.day,
                self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                tzinfo=ET
            )

            if now >= release_et:
                if release_date.month == 12:
                    next_release_month = date(release_date.year + 1, 2, 1)
                else:
                    next_release_month = date(release_date.year, release_date.month + 2, 1)

                last_day = next_release_month - timedelta(days=1)
                release_date = last_day
                while release_date.weekday() >= 5:
                    release_date -= timedelta(days=1)

            return {
                "date": release_date.strftime("%Y-%m-%d"),
                "label": f"Personal Income (estimated) - {release_date.strftime('%Y/%m/%d')} 8:30 ET"
            }

        except Exception as e:
            print(f"Error calculating fallback next release: {e}")
            return None

    def _get_cached_schedule(self) -> Optional[Dict[str, Any]]:
        """キャッシュされた発表スケジュールを取得"""
        try:
            if SCHEDULE_CACHE_FILE.exists():
                with open(SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _save_schedule_cache(self, data: Dict[str, Any]) -> None:
        """発表スケジュールをキャッシュに保存"""
        try:
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save schedule cache: {e}")

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
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
personal_income_service = PersonalIncomeService()
