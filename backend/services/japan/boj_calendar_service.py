"""
日銀発表スケジュール取得サービス

日銀公表予定ページから営業毎旬報告などの発表スケジュールを取得
https://www.boj.or.jp/about/calendar/index.htm

営業毎旬報告:
- 毎月10日、20日、月末時点のデータを発表
- 発表時刻: 10:00 JST
- 例: 2月13日 → 2月10日時点、2月25日 → 2月20日時点、3月3日 → 2月28日時点
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "calendar"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SCHEDULE_CACHE_FILE = CACHE_DIR / "boj_calendar_cache.json"

# Redis キャッシュキー
CACHE_KEY = "japan:boj_calendar:schedule"
CACHE_TTL = 86400  # 24時間


class BOJCalendarService:
    """日銀発表スケジュール取得サービス"""

    CALENDAR_URL = "https://www.boj.or.jp/about/calendar/index.htm"

    def get_eigyo_maijun_schedule(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        営業毎旬報告の発表スケジュールを取得

        Returns:
            {
                "schedule": [
                    {"date": "2026-02-13", "time": "10:00", "as_of": "2月10日"},
                    ...
                ],
                "next_release": {"date": "YYYY-MM-DD", "time": "10:00", "label": "..."},
                "cached": bool,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached = self._get_cached_schedule()
            if cached:
                # next_releaseを現在時刻に基づいて再計算
                schedule = cached.get("schedule", [])
                next_release = self._get_next_release_from_schedule(schedule)
                return {
                    "schedule": schedule,
                    "next_release": next_release,
                    "cached": True,
                    "last_updated": cached.get("last_updated")
                }

        # スクレイピングで取得
        schedule = self._scrape_eigyo_maijun_schedule()

        if schedule:
            cache_payload = {
                "schedule": schedule,
                "last_updated": datetime.now(JST).isoformat()
            }
            self._save_cache(cache_payload)

            next_release = self._get_next_release_from_schedule(schedule)
            return {
                "schedule": schedule,
                "next_release": next_release,
                "cached": False,
                "last_updated": cache_payload["last_updated"]
            }

        # フォールバック
        cached = self._load_file_cache()
        if cached:
            schedule = cached.get("schedule", [])
            next_release = self._get_next_release_from_schedule(schedule)
            return {
                "schedule": schedule,
                "next_release": next_release,
                "cached": True,
                "last_updated": cached.get("last_updated")
            }

        return {
            "schedule": [],
            "next_release": None,
            "cached": False,
            "last_updated": None,
            "error": "Failed to fetch schedule"
        }

    def _scrape_eigyo_maijun_schedule(self) -> List[Dict[str, Any]]:
        """日銀カレンダーページから営業毎旬報告のスケジュールをスクレイピング"""
        try:
            print("Fetching BOJ calendar from:", self.CALENDAR_URL)

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(self.CALENDAR_URL, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            schedule = []
            current_year = datetime.now(JST).year

            # テーブルから営業毎旬報告を探す
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    row_text = row.get_text()

                    # 営業毎旬報告の行を検出
                    if '営業毎旬報告' in row_text:
                        # 日付と時刻を抽出
                        for cell in cells:
                            cell_text = cell.get_text().strip()

                            # 日付パターン: "2月13日" や "3月3日"
                            date_match = re.search(r'(\d{1,2})月(\d{1,2})日', cell_text)
                            if date_match:
                                month = int(date_match.group(1))
                                day = int(date_match.group(2))

                                # 年を決定（現在月より前なら来年）
                                year = current_year
                                now = datetime.now(JST)
                                if month < now.month or (month == now.month and day < now.day):
                                    year = current_year + 1

                                date_str = f"{year}-{month:02d}-{day:02d}"

                                # 時刻抽出（通常10:00）
                                time_match = re.search(r'(\d{1,2}):(\d{2})', cell_text)
                                time_str = f"{time_match.group(1)}:{time_match.group(2)}" if time_match else "10:00"

                                # as_of（〇月〇日現在）を抽出
                                as_of_match = re.search(r'(\d{1,2})月(\d{1,2})日現在', cell_text)
                                as_of = f"{as_of_match.group(1)}月{as_of_match.group(2)}日" if as_of_match else None

                                schedule.append({
                                    "date": date_str,
                                    "time": time_str,
                                    "as_of": as_of
                                })

            # 日付でソート
            schedule.sort(key=lambda x: x["date"])

            # 重複除去
            seen = set()
            unique_schedule = []
            for item in schedule:
                if item["date"] not in seen:
                    seen.add(item["date"])
                    unique_schedule.append(item)

            print(f"Found {len(unique_schedule)} eigyo_maijun schedules")
            return unique_schedule

        except Exception as e:
            print(f"Error scraping BOJ calendar: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_next_release_from_schedule(
        self,
        schedule: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """スケジュールリストから次回発表日を取得"""
        if not schedule:
            return None

        now = datetime.now(JST)
        now_date = now.strftime("%Y-%m-%d")

        for item in schedule:
            release_date = item["date"]
            release_time = item.get("time", "10:00")

            # 発表日時を構築
            try:
                release_dt = datetime.strptime(
                    f"{release_date} {release_time}",
                    "%Y-%m-%d %H:%M"
                ).replace(tzinfo=JST)

                if release_dt > now:
                    return {
                        "date": release_date,
                        "time": release_time,
                        "datetime_jst": release_dt.isoformat(),
                        "as_of": item.get("as_of"),
                        "label": f"営業毎旬報告 ({item.get('as_of', '')}現在)"
                    }
            except ValueError:
                continue

        return None

    def get_next_eigyo_maijun_release(self) -> Optional[Dict[str, Any]]:
        """次回の営業毎旬報告発表日時を取得（簡易版）"""
        result = self.get_eigyo_maijun_schedule()
        return result.get("next_release")

    def _get_cached_schedule(self) -> Optional[Dict[str, Any]]:
        """Redisキャッシュからスケジュールを取得"""
        try:
            cached = redis_client.get(CACHE_KEY)
            if cached:
                return cached
        except Exception as e:
            print(f"Redis cache error: {e}")

        return self._load_file_cache()

    def _save_cache(self, data: Dict[str, Any]) -> None:
        """キャッシュを保存"""
        try:
            redis_client.set(CACHE_KEY, data, expire=CACHE_TTL)
        except Exception as e:
            print(f"Redis save error: {e}")

        self._save_file_cache(data)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if SCHEDULE_CACHE_FILE.exists():
                with open(SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"File cache load error: {e}")
        return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"File cache save error: {e}")


# シングルトンインスタンス
boj_calendar_service = BOJCalendarService()
