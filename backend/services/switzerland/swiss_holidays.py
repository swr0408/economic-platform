"""
スイス祝日取得モジュール

Nager.Date API（https://date.nager.at/API）からスイスの祝日を取得
チューリッヒ州（ZH）に適用される祝日のみをフィルタリング

キャッシュ:
- ファイルキャッシュ: 年に1回更新
- Redis: 24時間有効

参照:
- Nager.Date API: https://date.nager.at/api/v3/PublicHolidays/{year}/CH
- SNB銀行休業日: https://www.snb.ch/en/about-us/general-information/contact
"""
import json
from datetime import datetime
from typing import Set, Optional
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
HOLIDAYS_CACHE_FILE = CACHE_DIR / "swiss_holidays_cache.json"

REDIS_CACHE_KEY = "switzerland:holidays"
REDIS_CACHE_EXPIRE = 86400 * 30  # 30日

# Nager.Date API
NAGER_API_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/CH"

# チューリッヒ州コード
ZURICH_COUNTY = "CH-ZH"

# フォールバック用の静的祝日（API取得失敗時）
FALLBACK_HOLIDAYS = {
    # 2025年
    "2025-01-01",  # New Year's Day
    "2025-01-02",  # Berchtoldstag
    "2025-04-18",  # Good Friday
    "2025-04-21",  # Easter Monday
    "2025-05-01",  # Labour Day
    "2025-05-29",  # Ascension Day
    "2025-06-09",  # Whit Monday
    "2025-08-01",  # Swiss National Day
    "2025-12-25",  # Christmas Day
    "2025-12-26",  # St. Stephen's Day
    # 2026年
    "2026-01-01",  # New Year's Day
    "2026-01-02",  # Berchtoldstag
    "2026-04-03",  # Good Friday
    "2026-04-06",  # Easter Monday
    "2026-05-01",  # Labour Day
    "2026-05-14",  # Ascension Day
    "2026-05-25",  # Whit Monday
    "2026-08-01",  # Swiss National Day
    "2026-12-25",  # Christmas Day
    "2026-12-26",  # St. Stephen's Day
    # 2027年
    "2027-01-01",  # New Year's Day
    "2027-01-02",  # Berchtoldstag
    "2027-03-26",  # Good Friday
    "2027-03-29",  # Easter Monday
    "2027-05-01",  # Labour Day
    "2027-05-06",  # Ascension Day
    "2027-05-17",  # Whit Monday
    "2027-08-01",  # Swiss National Day
    "2027-12-25",  # Christmas Day
    "2027-12-26",  # St. Stephen's Day
}


class SwissHolidaysService:
    """スイス祝日サービス"""

    def __init__(self):
        self._holidays_cache: Optional[Set[str]] = None

    def get_holidays(self, year: Optional[int] = None) -> Set[str]:
        """スイス（チューリッヒ州）の祝日を取得

        Args:
            year: 取得する年（Noneの場合は今年と来年）

        Returns:
            祝日の日付セット（"YYYY-MM-DD"形式）
        """
        # メモリキャッシュ
        if self._holidays_cache:
            if year:
                return {h for h in self._holidays_cache if h.startswith(str(year))}
            return self._holidays_cache

        # Redisキャッシュ
        cached = redis_client.get(REDIS_CACHE_KEY)
        if cached:
            holidays = set(cached.get("holidays", []))
            cache_year = cached.get("year")
            current_year = datetime.now(JST).year

            # キャッシュが現在の年のデータを含んでいれば使用
            if cache_year and cache_year >= current_year:
                self._holidays_cache = holidays
                if year:
                    return {h for h in holidays if h.startswith(str(year))}
                return holidays

        # ファイルキャッシュ
        file_cache = self._load_file_cache()
        if file_cache:
            holidays = set(file_cache.get("holidays", []))
            cache_year = file_cache.get("year")
            current_year = datetime.now(JST).year

            if cache_year and cache_year >= current_year:
                self._holidays_cache = holidays
                redis_client.set(REDIS_CACHE_KEY, file_cache, expire=REDIS_CACHE_EXPIRE)
                if year:
                    return {h for h in holidays if h.startswith(str(year))}
                return holidays

        # APIから取得
        holidays = self._fetch_from_api()
        if holidays:
            self._holidays_cache = holidays
            if year:
                return {h for h in holidays if h.startswith(str(year))}
            return holidays

        # フォールバック
        print("[SwissHolidays] Using fallback holidays")
        return FALLBACK_HOLIDAYS

    def _fetch_from_api(self) -> Set[str]:
        """Nager.Date APIからスイス祝日を取得

        今年と来年の祝日を取得し、チューリッヒ州に適用されるものをフィルタ
        """
        current_year = datetime.now(JST).year
        all_holidays = set()

        for year in [current_year, current_year + 1, current_year + 2]:
            try:
                url = NAGER_API_URL.format(year=year)
                print(f"[SwissHolidays] Fetching: {url}")

                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                for holiday in data:
                    # typeが"Public"のみを対象
                    if "Public" not in holiday.get("types", []):
                        continue

                    counties = holiday.get("counties")
                    date = holiday.get("date")

                    if not date:
                        continue

                    # 全国適用（counties=null）またはチューリッヒ州適用
                    if counties is None or ZURICH_COUNTY in counties:
                        all_holidays.add(date)
                        print(f"[SwissHolidays] Added: {date} - {holiday.get('name')}")

            except Exception as e:
                print(f"[SwissHolidays] Error fetching {year}: {e}")
                continue

        if all_holidays:
            # キャッシュに保存
            cache_data = {
                "holidays": sorted(list(all_holidays)),
                "year": current_year,
                "fetched_at": datetime.now(JST).isoformat(),
            }
            redis_client.set(REDIS_CACHE_KEY, cache_data, expire=REDIS_CACHE_EXPIRE)
            self._save_file_cache(cache_data)

        return all_holidays

    def _load_file_cache(self) -> Optional[dict]:
        """ファイルキャッシュを読み込む"""
        try:
            if not HOLIDAYS_CACHE_FILE.exists():
                return None
            with open(HOLIDAYS_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SwissHolidays] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: dict) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(HOLIDAYS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[SwissHolidays] Saved {len(data.get('holidays', []))} holidays to cache")
        except Exception as e:
            print(f"[SwissHolidays] Failed to save file cache: {e}")

    def is_holiday(self, date: datetime) -> bool:
        """指定日がスイスの祝日かどうかを判定

        Args:
            date: 判定する日付

        Returns:
            祝日の場合True
        """
        date_str = date.strftime("%Y-%m-%d")
        holidays = self.get_holidays(date.year)
        return date_str in holidays

    def refresh(self) -> bool:
        """祝日データを強制更新

        Returns:
            更新成功時True
        """
        self._holidays_cache = None
        redis_client.delete(REDIS_CACHE_KEY)

        holidays = self._fetch_from_api()
        return len(holidays) > 0


# シングルトンインスタンス
swiss_holidays_service = SwissHolidaysService()


def get_swiss_holidays(year: Optional[int] = None) -> Set[str]:
    """スイス祝日を取得（ヘルパー関数）"""
    return swiss_holidays_service.get_holidays(year)


def is_swiss_holiday(date: datetime) -> bool:
    """スイス祝日判定（ヘルパー関数）"""
    return swiss_holidays_service.is_holiday(date)
