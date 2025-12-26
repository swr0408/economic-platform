"""
新規失業保険申請件数（UI Initial Claims）サービス
FRED APIから新規失業保険申請件数データを取得

指標:
- ICSA: Initial Claims, Weekly, Seasonally Adjusted
- IC4WSA: 4-Week Moving Average of Initial Claims, Weekly, Seasonally Adjusted

データソース:
- FRED: https://fred.stlouisfed.org/series/ICSA
- DOL: https://oui.doleta.gov/unemploy/claims_arch.asp

発表スケジュール:
- 毎週木曜日 8:30 AM ET
- 祝日による例外日あり（DOLサイトからスクレイピング、月1回更新）

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import json
import re
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
ICSA_SERIES_ID = "ICSA"         # 新規失業保険申請件数
IC4WSA_SERIES_ID = "IC4WSA"     # 4週移動平均

# DOLスケジュールページURL（例外日が掲載されている）
DOL_SCHEDULE_URL = "https://oui.doleta.gov/unemploy/claims_arch.asp"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "initial_claims_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "initial_claims_schedule.json"

# User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.7",
}


class InitialClaimsService:
    """新規失業保険申請件数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:initial_claims:data"
    SCHEDULE_CACHE_KEY = "dol:initial_claims:schedule"

    # 発表時刻設定（ET）- 8:30 AM ET
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_initial_claims_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        新規失業保険申請件数データを取得

        Returns:
            {
                "data": [{"date": str, "icsa": float, "ic4wsa": float}, ...],
                "latest": {...},
                "next_release": {"date": str, "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, next_release):
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
                if last_updated_str and not self._should_refresh(last_updated_str, next_release):
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
        icsa_data = self._fetch_series_from_api(ICSA_SERIES_ID, start_date)
        ic4wsa_data = self._fetch_series_from_api(IC4WSA_SERIES_ID, start_date)

        if icsa_data:
            # データを結合
            combined_data = self._combine_data(icsa_data, ic4wsa_data)
            latest = combined_data[-1] if combined_data else None

            cache_payload = {
                "data": combined_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": combined_data,
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

    def _fetch_series_from_api(self, series_id: str, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから指定シリーズのデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print(f"Fetching {series_id} from FRED...")

            if not start_date:
                start_date = "2000-01-01"

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
                        "value": round(value, 0)  # 実数（件）
                    })
                except (ValueError, KeyError):
                    continue

            print(f"Fetched {len(result)} {series_id} records")
            return result

        except Exception as e:
            print(f"Error fetching {series_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _combine_data(
        self,
        icsa_data: List[Dict[str, Any]],
        ic4wsa_data: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """ICSAとIC4WSAのデータを結合"""
        # ICSAをベースにする
        icsa_map = {d["date"]: d["value"] for d in icsa_data}

        # IC4WSAをマップに変換
        ic4wsa_map = {}
        if ic4wsa_data:
            ic4wsa_map = {d["date"]: d["value"] for d in ic4wsa_data}

        # 全ての日付を取得
        all_dates = sorted(set(icsa_map.keys()) | set(ic4wsa_map.keys()))

        result = []
        for dt in all_dates:
            icsa_value = icsa_map.get(dt)
            ic4wsa_value = ic4wsa_map.get(dt)

            if icsa_value is not None:  # ICSAがある場合のみ含める
                result.append({
                    "date": dt,
                    "icsa": icsa_value,
                    "ic4wsa": ic4wsa_value
                })

        return result

    def _should_refresh(self, last_updated_str: str, next_release: Optional[Dict[str, Any]]) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

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
                    print(f"[Initial Claims] Release time passed: {release_jst}, last_updated: {last_updated}")
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得

        優先順位:
        1. DOLサイトからスクレイピングした例外日リスト
        2. 通常スケジュール（毎週木曜日）から計算
        """
        try:
            today = date.today()

            # キャッシュチェック
            cached_schedule = self._get_cached_schedule()
            exception_dates = {}

            if cached_schedule:
                exception_dates = cached_schedule.get("exception_dates", {})
            else:
                # DOLからスクレイピング（月1回）
                exception_dates = self._fetch_exception_dates()
                if exception_dates:
                    self._save_schedule_cache({"exception_dates": exception_dates})

            # 今日から4週間先までをチェック
            for i in range(28):
                check_date = today + timedelta(days=i)

                # 例外日に該当する場合
                check_date_str = check_date.strftime("%Y-%m-%d")
                if check_date_str in exception_dates:
                    return {
                        "date": check_date_str,
                        "label": f"失業保険申請件数 - {check_date.strftime('%Y/%m/%d')} 8:30 ET (例外日)"
                    }

                # 通常スケジュール（木曜日 = weekday 3）
                if check_date.weekday() == 3:
                    # この木曜日が例外日リストにある場合、例外日の方が発表日
                    # 例外日でこの木曜日がスキップされているかチェック
                    is_exception_week = False
                    for exc_date_str in exception_dates.keys():
                        exc_date = datetime.strptime(exc_date_str, "%Y-%m-%d").date()
                        # 同じ週かどうかをチェック
                        if abs((exc_date - check_date).days) <= 3:
                            is_exception_week = True
                            break

                    if not is_exception_week:
                        return {
                            "date": check_date_str,
                            "label": f"失業保険申請件数 - {check_date.strftime('%Y/%m/%d')} 8:30 ET"
                        }

            return None

        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

    def _fetch_exception_dates(self) -> Dict[str, str]:
        """
        DOLサイトから例外日をスクレイピング

        Returns:
            {"2025-01-08": "Wednesday", "2025-06-18": "Wednesday", ...}
        """
        try:
            print("Fetching exception dates from DOL...")

            response = requests.get(DOL_SCHEDULE_URL, headers=HEADERS, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()

            exception_dates = {}

            # 例外日のパターンを検索
            # 例: "Wednesday, January 8, 2025"
            month_names = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12
            }

            # パターン: "Weekday, Month DD, YYYY"
            pattern = r'(Monday|Tuesday|Wednesday|Friday),?\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})'
            matches = re.findall(pattern, text, re.IGNORECASE)

            current_year = datetime.now().year

            for match in matches:
                weekday = match[0]
                month_name = match[1].lower()
                day = int(match[2])
                year = int(match[3])

                if month_name in month_names and year >= current_year:
                    month = month_names[month_name]
                    date_str = f"{year:04d}-{month:02d}-{day:02d}"
                    exception_dates[date_str] = weekday

            print(f"Found {len(exception_dates)} exception dates: {list(exception_dates.keys())}")
            return exception_dates

        except Exception as e:
            print(f"Error fetching exception dates: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _get_cached_schedule(self) -> Optional[Dict[str, Any]]:
        """キャッシュされた例外日スケジュールを取得"""
        # Redisチェック
        cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached:
            cached_at = cached.get("cached_at")
            if cached_at:
                try:
                    cached_dt = datetime.fromisoformat(cached_at)
                    if cached_dt.tzinfo is None:
                        cached_dt = cached_dt.replace(tzinfo=JST)
                    # 30日間有効（月1回更新）
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
        """例外日スケジュールをキャッシュに保存"""
        try:
            data["cached_at"] = datetime.now(JST).isoformat()
            redis_client.set(self.SCHEDULE_CACHE_KEY, data, expire=30*24*60*60)

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Initial Claims schedule cache saved to {SCHEDULE_CACHE_FILE}")
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
            print(f"Initial Claims cache saved to {DATA_CACHE_FILE}")
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
            "indicator": "Initial Claims (UI Weekly Claims)",
            "source": "FRED / DOL",
            "series_ids": [ICSA_SERIES_ID, IC4WSA_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
initial_claims_service = InitialClaimsService()
