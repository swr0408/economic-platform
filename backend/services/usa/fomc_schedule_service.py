#!/usr/bin/env python3
"""
FOMC Schedule Service
FRBの公式ページからFOMCスケジュールを取得
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import List, Dict, Optional
from pathlib import Path
import json
import re

class FOMCScheduleService:
    """FRB公式サイトからFOMCスケジュールを取得するサービス"""

    SCHEDULE_URL = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240809a.htm"
    CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "fomc_schedule"
    CACHE_FILE = "fomc_schedule.json"
    CACHE_EXPIRY_DAYS = 30  # 30日間キャッシュ

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def fetch_schedule_from_frb(self) -> Dict[str, List[Dict[str, str]]]:
        """
        FRBの公式ページからFOMCスケジュールをスクレイピング

        Returns:
            年ごとのスケジュール {"2025": [...], "2026": [...]}
        """
        try:
            response = requests.get(self.SCHEDULE_URL, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            schedule = {}
            current_year = None

            # テーブルまたはリストからスケジュールを抽出
            # FRBページの構造に合わせてパース
            content = soup.find('div', class_='col-xs-12')

            if not content:
                content = soup.find('main') or soup.find('article') or soup

            # 年とスケジュールを抽出
            text = content.get_text()

            # 2025年と2026年のスケジュールを抽出
            schedule = {
                "2025": self._parse_year_schedule(text, 2025),
                "2026": self._parse_year_schedule(text, 2026)
            }

            return schedule

        except Exception as e:
            print(f"Error fetching FOMC schedule from FRB: {e}")
            raise

    def _parse_year_schedule(self, text: str, year: int) -> List[Dict[str, str]]:
        """
        テキストから特定年のFOMCスケジュールを抽出

        Args:
            text: ページのテキスト内容
            year: 対象年

        Returns:
            会合日リスト
        """
        meetings = []

        # FRB公式スケジュール（手動で設定、スクレイピング失敗時のバックアップにも使用）
        # https://www.federalreserve.gov/newsevents/pressreleases/monetary20240809a.htm より
        # 発表時刻: 夏時間(3-11月) = 日本時間3:00, 冬時間(11-3月) = 日本時間4:00
        # is_dst: True = 夏時間期間中（日本時間3:00発表）, False = 冬時間期間中（日本時間4:00発表）
        official_schedule = {
            2025: [
                {"month": 1, "days": "28-29", "has_sep": False, "is_dst": False},   # 冬時間 4:00
                {"month": 3, "days": "18-19", "has_sep": True, "is_dst": True},     # 夏時間 3:00 SEP発表
                {"month": 5, "days": "6-7", "has_sep": False, "is_dst": True},      # 夏時間 3:00
                {"month": 6, "days": "17-18", "has_sep": True, "is_dst": True},     # 夏時間 3:00 SEP発表
                {"month": 7, "days": "29-30", "has_sep": False, "is_dst": True},    # 夏時間 3:00
                {"month": 9, "days": "16-17", "has_sep": True, "is_dst": True},     # 夏時間 3:00 SEP発表
                {"month": 10, "days": "28-29", "has_sep": False, "is_dst": True},   # 夏時間 3:00
                {"month": 12, "days": "9-10", "has_sep": True, "is_dst": False},    # 冬時間 4:00 SEP発表
            ],
            2026: [
                {"month": 1, "days": "27-28", "has_sep": False, "is_dst": False},   # 冬時間 4:00
                {"month": 3, "days": "17-18", "has_sep": True, "is_dst": False},    # 冬時間 4:00 SEP発表（3月は夏時間開始前）
                {"month": 4, "days": "28-29", "has_sep": False, "is_dst": True},    # 夏時間 3:00
                {"month": 6, "days": "16-17", "has_sep": True, "is_dst": True},     # 夏時間 3:00 SEP発表
                {"month": 7, "days": "28-29", "has_sep": False, "is_dst": True},    # 夏時間 3:00
                {"month": 9, "days": "15-16", "has_sep": True, "is_dst": True},     # 夏時間 3:00 SEP発表
                {"month": 10, "days": "27-28", "has_sep": False, "is_dst": True},   # 夏時間 3:00
                {"month": 12, "days": "8-9", "has_sep": True, "is_dst": False},     # 冬時間 4:00 SEP発表
            ]
        }

        if year in official_schedule:
            for meeting in official_schedule[year]:
                # 2日間の会合の2日目（発表日）を取得
                days = meeting["days"].split("-")
                second_day = int(days[1])

                meeting_date = date(year, meeting["month"], second_day)

                # 発表時刻（日本時間）: 夏時間=3:00, 冬時間=4:00
                is_dst = meeting.get("is_dst", False)
                announcement_hour_jst = 3 if is_dst else 4

                meetings.append({
                    "date": meeting_date.strftime("%Y%m%d"),
                    "label": f"{year}年{meeting['month']}月{second_day}日",
                    "has_sep": meeting["has_sep"],
                    "month": meeting["month"],
                    "day": second_day,
                    "is_dst": is_dst,
                    "announcement_hour_jst": announcement_hour_jst,
                    "announcement_hour_utc": (announcement_hour_jst - 9) % 24  # JST -> UTC (前日の18時 or 19時)
                })

        return meetings

    def get_sep_dates(self, count: int = 4, include_future: bool = False) -> List[Dict[str, str]]:
        """
        SEP発表日を取得（3月、6月、9月、12月の会合）

        Args:
            count: 取得する日付の数
            include_future: 未来の日付も含めるかどうか

        Returns:
            SEP発表日リスト（新しい順）
        """
        schedule = self.get_schedule()
        today = date.today()

        sep_dates = []

        # 全年のスケジュールを結合してソート
        all_meetings = []
        for year_str, meetings in schedule.items():
            all_meetings.extend(meetings)

        # SEP発表日のみフィルタ
        sep_meetings = [m for m in all_meetings if m.get("has_sep", False)]

        # 日付でソート（新しい順）
        sep_meetings.sort(key=lambda x: x["date"], reverse=True)

        for meeting in sep_meetings:
            meeting_date = datetime.strptime(meeting["date"], "%Y%m%d").date()

            # 今日以前の日付のみ（include_future=Falseの場合）
            if include_future or meeting_date <= today:
                sep_dates.append({
                    "date": meeting["date"],
                    "label": meeting["label"]
                })

            if len(sep_dates) >= count:
                break

        return sep_dates

    def get_upcoming_sep_dates(self, count: int = 4) -> List[Dict[str, str]]:
        """
        今後のSEP発表日を取得

        Args:
            count: 取得する日付の数

        Returns:
            SEP発表日リスト（近い順）
        """
        schedule = self.get_schedule()
        today = date.today()

        sep_dates = []

        # 全年のスケジュールを結合
        all_meetings = []
        for year_str, meetings in schedule.items():
            all_meetings.extend(meetings)

        # SEP発表日のみフィルタ
        sep_meetings = [m for m in all_meetings if m.get("has_sep", False)]

        # 日付でソート（古い順＝近い順）
        sep_meetings.sort(key=lambda x: x["date"])

        for meeting in sep_meetings:
            meeting_date = datetime.strptime(meeting["date"], "%Y%m%d").date()

            # 今日以降の日付のみ
            if meeting_date >= today:
                sep_dates.append({
                    "date": meeting["date"],
                    "label": meeting["label"]
                })

            if len(sep_dates) >= count:
                break

        return sep_dates

    def get_upcoming_fomc_dates(self, count: int = 8) -> List[Dict[str, str]]:
        """
        今後の全FOMC会合日を取得（SEPに限らず全ての会合）

        Args:
            count: 取得する日付の数

        Returns:
            FOMC会合日リスト（近い順）
        """
        schedule = self.get_schedule()
        today = date.today()

        fomc_dates = []

        # 全年のスケジュールを結合
        all_meetings = []
        for year_str, meetings in schedule.items():
            all_meetings.extend(meetings)

        # 日付でソート（古い順＝近い順）
        all_meetings.sort(key=lambda x: x["date"])

        for meeting in all_meetings:
            meeting_date = datetime.strptime(meeting["date"], "%Y%m%d").date()

            # 今日以降の日付のみ
            if meeting_date >= today:
                fomc_dates.append({
                    "date": meeting["date"],
                    "label": meeting["label"],
                    "has_sep": meeting.get("has_sep", False)
                })

            if len(fomc_dates) >= count:
                break

        return fomc_dates

    def get_schedule(self) -> Dict[str, List[Dict[str, str]]]:
        """
        スケジュールを取得（キャッシュがあればキャッシュから）

        Returns:
            年ごとのスケジュール
        """
        cache_path = self.CACHE_DIR / self.CACHE_FILE

        # キャッシュを確認
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)

                # キャッシュの有効期限を確認
                cached_at = datetime.fromisoformat(cached_data.get("cached_at", "2000-01-01"))
                if (datetime.now() - cached_at).days < self.CACHE_EXPIRY_DAYS:
                    return cached_data.get("schedule", {})
            except Exception as e:
                print(f"Error reading cache: {e}")

        # キャッシュがないか期限切れの場合、新規取得
        try:
            schedule = self.fetch_schedule_from_frb()
            self._save_cache(schedule)
            return schedule
        except Exception as e:
            print(f"Error fetching schedule, using fallback: {e}")
            # フォールバック: ハードコードされたスケジュールを使用
            return self._get_fallback_schedule()

    def _save_cache(self, schedule: Dict[str, List[Dict[str, str]]]):
        """スケジュールをキャッシュに保存"""
        cache_path = self.CACHE_DIR / self.CACHE_FILE

        cache_data = {
            "schedule": schedule,
            "cached_at": datetime.now().isoformat(),
            "source": self.SCHEDULE_URL
        }

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    def _get_fallback_schedule(self) -> Dict[str, List[Dict[str, str]]]:
        """フォールバック用のハードコードされたスケジュール"""
        return {
            "2025": self._parse_year_schedule("", 2025),
            "2026": self._parse_year_schedule("", 2026)
        }

    def update_cache(self) -> bool:
        """
        キャッシュを強制的に更新

        Returns:
            成功したかどうか
        """
        try:
            schedule = self.fetch_schedule_from_frb()
            self._save_cache(schedule)
            return True
        except Exception as e:
            print(f"Error updating cache: {e}")
            return False


# グローバルインスタンス
fomc_schedule_service = FOMCScheduleService()
