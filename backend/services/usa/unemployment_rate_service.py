"""
失業率 / 広義の失業率サービス
FRED APIからUNRATE & U6RATEデータを取得

指標:
- UNRATE: Unemployment Rate（失業率）
- U6RATE: Total Unemployed Plus All Persons Marginally Attached to the Labor Force Plus Total Employed Part Time for Economic Reasons（広義の失業率）

データソース:
- FRED: https://fred.stlouisfed.org/series/UNRATE
- FRED: https://fred.stlouisfed.org/series/U6RATE
- BLS: https://www.bls.gov/schedule/news_release/empsit.htm

発表スケジュール:
- BLS Employment Situation（雇用統計）
- 毎月第1金曜日 8:30 AM ET
- BLSから次回発表日を自動取得

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
UNRATE_SERIES_ID = "UNRATE"     # 失業率
U6RATE_SERIES_ID = "U6RATE"     # 広義の失業率（U-6）

# BLS Employment Situation リリーススケジュールURL
BLS_EMPSIT_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/empsit.htm"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "unemployment_rate_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "bls_empsit_schedule.json"

# 月名マッピング
MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9,
    'oct': 10, 'nov': 11, 'dec': 12
}


class UnemploymentRateService:
    """失業率 / 広義の失業率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:unemployment_rate:data"
    SCHEDULE_CACHE_KEY = "bls:empsit:schedule"

    # 発表時刻設定（ET）- 8:30 AM ET
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 30

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
        """次回発表日を取得（BLSからスクレイピング）"""
        try:
            # キャッシュチェック
            cached_schedule = self._get_cached_schedule()
            if cached_schedule:
                # 次回発表日を探す
                today = date.today()
                for release in cached_schedule.get("releases", []):
                    release_date_str = release.get("date")
                    if release_date_str:
                        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                        if release_date >= today:
                            return release

            # BLSページからスクレイピング
            releases = self._fetch_bls_schedule()
            if releases:
                # キャッシュに保存
                self._save_schedule_cache({"releases": releases})

                # 次回発表日を返す
                today = date.today()
                for release in releases:
                    release_date_str = release.get("date")
                    if release_date_str:
                        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                        if release_date >= today:
                            return release

            return self._calculate_next_release_fallback()

        except Exception as e:
            print(f"Error getting next release: {e}")
            return self._calculate_next_release_fallback()

    def _fetch_bls_schedule(self) -> List[Dict[str, Any]]:
        """BLS Employment Situationスケジュールをスクレイピング"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }

            response = requests.get(BLS_EMPSIT_SCHEDULE_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            releases = []

            # テーブルからデータを抽出
            # BLSのスケジュールページはテーブル形式で発表日を記載
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # 日付パターンを探す（例: "January 10, 2025"）
                        text = cells[0].get_text(strip=True)
                        match = re.search(r'(\w+)\s+(\d{1,2}),?\s*(\d{4})', text)
                        if match:
                            month_name = match.group(1).lower()
                            day = int(match.group(2))
                            year = int(match.group(3))

                            month_num = MONTH_MAP.get(month_name)
                            if month_num:
                                try:
                                    release_date = date(year, month_num, day)
                                    releases.append({
                                        "date": release_date.strftime("%Y-%m-%d"),
                                        "label": f"Employment Situation - {release_date.strftime('%Y/%m/%d')} 8:30 ET"
                                    })
                                except ValueError:
                                    continue

            # 日付順にソート
            releases.sort(key=lambda x: x["date"])

            if releases:
                print(f"Fetched {len(releases)} BLS Employment Situation release dates")

            return releases

        except Exception as e:
            print(f"Error fetching BLS schedule: {e}")
            return []

    def _calculate_next_release_fallback(self) -> Optional[Dict[str, Any]]:
        """次回発表日のフォールバック計算（毎月第1金曜日）"""
        try:
            now = datetime.now(ET)
            today = now.date()

            # 今月の第1金曜日を計算
            first_friday = self._get_first_friday(today.year, today.month)

            # 今月の第1金曜日の発表時刻
            release_et = datetime(
                first_friday.year, first_friday.month, first_friday.day,
                self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                tzinfo=ET
            )

            # 現在時刻が今月の発表時刻を過ぎている場合は来月
            if now >= release_et:
                if today.month == 12:
                    next_month_year = today.year + 1
                    next_month = 1
                else:
                    next_month_year = today.year
                    next_month = today.month + 1
                first_friday = self._get_first_friday(next_month_year, next_month)

            return {
                "date": first_friday.strftime("%Y-%m-%d"),
                "label": f"Employment Situation (estimated) - {first_friday.strftime('%Y/%m/%d')} 8:30 ET"
            }

        except Exception as e:
            print(f"Error calculating fallback next release: {e}")
            return None

    def _get_first_friday(self, year: int, month: int) -> date:
        """指定月の第1金曜日を取得"""
        first_day = date(year, month, 1)
        # 金曜日 = 4 (0=月曜日)
        days_until_friday = (4 - first_day.weekday() + 7) % 7
        if days_until_friday == 0:
            # 1日が金曜日の場合
            return first_day
        return first_day + timedelta(days=days_until_friday)

    def _get_cached_schedule(self) -> Optional[Dict[str, Any]]:
        """キャッシュされた発表スケジュールを取得"""
        # Redisチェック
        cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached:
            cached_at = cached.get("cached_at")
            if cached_at:
                try:
                    cached_dt = datetime.fromisoformat(cached_at)
                    if cached_dt.tzinfo is None:
                        cached_dt = cached_dt.replace(tzinfo=JST)
                    # 30日間有効
                    if (datetime.now(JST) - cached_dt).days < 30:
                        return cached
                except Exception:
                    pass

        # ファイルキャッシュチェック
        try:
            if SCHEDULE_CACHE_FILE.exists():
                with open(SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                    file_cache = json.load(f)
                    cached_at = file_cache.get("cached_at")
                    if cached_at:
                        cached_dt = datetime.fromisoformat(cached_at)
                        if cached_dt.tzinfo is None:
                            cached_dt = cached_dt.replace(tzinfo=JST)
                        if (datetime.now(JST) - cached_dt).days < 30:
                            redis_client.set(self.SCHEDULE_CACHE_KEY, file_cache, expire=30*24*60*60)
                            return file_cache
        except Exception:
            pass

        return None

    def _save_schedule_cache(self, data: Dict[str, Any]) -> None:
        """発表スケジュールをキャッシュに保存"""
        try:
            data["cached_at"] = datetime.now(JST).isoformat()
            redis_client.set(self.SCHEDULE_CACHE_KEY, data, expire=30*24*60*60)

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
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Unemployment Rate",
            "source": "FRED / BLS",
            "series_ids": [UNRATE_SERIES_ID, U6RATE_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
unemployment_rate_service = UnemploymentRateService()
