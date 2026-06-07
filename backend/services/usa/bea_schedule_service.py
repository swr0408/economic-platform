#!/usr/bin/env python3
"""
BEA (Bureau of Economic Analysis) Release Schedule Service
GDP発表スケジュール・Personal Income発表スケジュールをBEA公式サイトからスクレイピング・管理

キャッシュ方式: ファイルキャッシュ（180日）
自動更新: 年2回（1月、7月）にスケジュールを更新
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import json
import re
from zoneinfo import ZoneInfo

# タイムゾーン
ET = ZoneInfo("America/New_York")
JST = ZoneInfo("Asia/Tokyo")


class BEAScheduleService:
    """BEA公式サイトからGDP・Personal Income発表スケジュールを取得するサービス"""

    SCHEDULE_URL = "https://www.bea.gov/news/schedule"
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "bea_schedule"
    CACHE_FILE = "gdp_schedule.json"
    PERSONAL_INCOME_CACHE_FILE = "personal_income_schedule.json"
    CACHE_EXPIRY_DAYS = 180  # 半年間キャッシュ

    # BEA発表時刻（米東部時間）
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def fetch_schedule_from_bea(self) -> List[Dict[str, str]]:
        """
        BEA公式ページからGDP発表スケジュールをスクレイピング

        Returns:
            GDP発表スケジュールのリスト
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(self.SCHEDULE_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            gdp_releases = []

            # テーブルからスケジュールを抽出
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # 日付とタイトルを取得
                        date_text = cells[0].get_text(strip=True)
                        title_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""

                        # GDPに関連するエントリをフィルタ
                        if 'Gross Domestic Product' in title_text or 'GDP' in title_text:
                            parsed_date = self._parse_date(date_text)
                            if parsed_date:
                                gdp_releases.append({
                                    "date": parsed_date.strftime("%Y-%m-%d"),
                                    "date_str": date_text,
                                    "title": title_text,
                                    "estimate_type": self._extract_estimate_type(title_text),
                                    "quarter": self._extract_quarter(title_text),
                                    "year": self._extract_year(title_text, parsed_date)
                                })

            # 日付でソート
            gdp_releases.sort(key=lambda x: x["date"])

            if gdp_releases:
                print(f"Fetched {len(gdp_releases)} GDP releases from BEA")
                return gdp_releases

            # スクレイピング失敗時はフォールバックを使用
            print("No GDP releases found via scraping, using fallback schedule")
            return self._get_fallback_schedule()

        except Exception as e:
            print(f"Error fetching BEA schedule: {e}")
            return self._get_fallback_schedule()

    def _parse_date(self, date_text: str) -> Optional[date]:
        """
        日付文字列をパース

        Args:
            date_text: "December 23, 2025" or "Dec 23, 2025" 形式

        Returns:
            date オブジェクト
        """
        try:
            # 様々なフォーマットを試行
            formats = [
                "%B %d, %Y",      # December 23, 2025
                "%b %d, %Y",      # Dec 23, 2025
                "%m/%d/%Y",       # 12/23/2025
                "%Y-%m-%d",       # 2025-12-23
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_text.strip(), fmt).date()
                except ValueError:
                    continue

            return None
        except Exception:
            return None

    def _extract_estimate_type(self, title: str) -> str:
        """
        発表タイプを抽出（Advance, Second, Third/Final）
        """
        title_lower = title.lower()
        if 'advance' in title_lower:
            return 'advance'
        elif 'second' in title_lower or '2nd' in title_lower:
            return 'second'
        elif 'third' in title_lower or '3rd' in title_lower or 'final' in title_lower:
            return 'third'
        elif 'initial' in title_lower:
            return 'initial'
        return 'unknown'

    def _extract_quarter(self, title: str) -> Optional[int]:
        """
        四半期を抽出
        """
        title_lower = title.lower()
        if '1st quarter' in title_lower or 'first quarter' in title_lower or 'q1' in title_lower:
            return 1
        elif '2nd quarter' in title_lower or 'second quarter' in title_lower or 'q2' in title_lower:
            return 2
        elif '3rd quarter' in title_lower or 'third quarter' in title_lower or 'q3' in title_lower:
            return 3
        elif '4th quarter' in title_lower or 'fourth quarter' in title_lower or 'q4' in title_lower:
            return 4
        return None

    def _extract_year(self, title: str, release_date: date) -> int:
        """
        対象年を抽出
        """
        # タイトルから年を抽出
        match = re.search(r'20\d{2}', title)
        if match:
            return int(match.group())
        # 抽出できない場合は発表日の年を使用
        return release_date.year

    def _get_fallback_schedule(self) -> List[Dict[str, str]]:
        """
        フォールバック用のハードコードされたスケジュール
        BEAの標準的な発表パターンに基づく

        GDP発表パターン:
        - Q1: 4月末(Advance), 5月末(Second), 6月末(Third)
        - Q2: 7月末(Advance), 8月末(Second), 9月末(Third)
        - Q3: 10月末(Advance), 11月末(Second), 12月末(Third)
        - Q4: 1月末(Advance), 2月末(Second), 3月末(Third)
        """
        current_year = datetime.now().year
        schedule = []

        # 2025年、2026年のスケジュールを生成
        for year in [current_year, current_year + 1]:
            # Q4 (前年) の発表 - 1月〜3月
            schedule.extend([
                {"date": f"{year}-01-30", "date_str": f"January 30, {year}",
                 "title": f"Gross Domestic Product, 4th Quarter {year-1} (Advance Estimate)",
                 "estimate_type": "advance", "quarter": 4, "year": year - 1},
                {"date": f"{year}-02-27", "date_str": f"February 27, {year}",
                 "title": f"Gross Domestic Product, 4th Quarter {year-1} (Second Estimate)",
                 "estimate_type": "second", "quarter": 4, "year": year - 1},
                {"date": f"{year}-03-27", "date_str": f"March 27, {year}",
                 "title": f"Gross Domestic Product, 4th Quarter {year-1} (Third Estimate)",
                 "estimate_type": "third", "quarter": 4, "year": year - 1},
            ])

            # Q1の発表 - 4月〜6月
            schedule.extend([
                {"date": f"{year}-04-24", "date_str": f"April 24, {year}",
                 "title": f"Gross Domestic Product, 1st Quarter {year} (Advance Estimate)",
                 "estimate_type": "advance", "quarter": 1, "year": year},
                {"date": f"{year}-05-29", "date_str": f"May 29, {year}",
                 "title": f"Gross Domestic Product, 1st Quarter {year} (Second Estimate)",
                 "estimate_type": "second", "quarter": 1, "year": year},
                {"date": f"{year}-06-26", "date_str": f"June 26, {year}",
                 "title": f"Gross Domestic Product, 1st Quarter {year} (Third Estimate)",
                 "estimate_type": "third", "quarter": 1, "year": year},
            ])

            # Q2の発表 - 7月〜9月
            schedule.extend([
                {"date": f"{year}-07-31", "date_str": f"July 31, {year}",
                 "title": f"Gross Domestic Product, 2nd Quarter {year} (Advance Estimate)",
                 "estimate_type": "advance", "quarter": 2, "year": year},
                {"date": f"{year}-08-28", "date_str": f"August 28, {year}",
                 "title": f"Gross Domestic Product, 2nd Quarter {year} (Second Estimate)",
                 "estimate_type": "second", "quarter": 2, "year": year},
                {"date": f"{year}-09-25", "date_str": f"September 25, {year}",
                 "title": f"Gross Domestic Product, 2nd Quarter {year} (Third Estimate)",
                 "estimate_type": "third", "quarter": 2, "year": year},
            ])

            # Q3の発表 - 10月〜12月
            schedule.extend([
                {"date": f"{year}-10-30", "date_str": f"October 30, {year}",
                 "title": f"Gross Domestic Product, 3rd Quarter {year} (Advance Estimate)",
                 "estimate_type": "advance", "quarter": 3, "year": year},
                {"date": f"{year}-11-27", "date_str": f"November 27, {year}",
                 "title": f"Gross Domestic Product, 3rd Quarter {year} (Second Estimate)",
                 "estimate_type": "second", "quarter": 3, "year": year},
                {"date": f"{year}-12-23", "date_str": f"December 23, {year}",
                 "title": f"Gross Domestic Product, 3rd Quarter {year} (Third Estimate)",
                 "estimate_type": "third", "quarter": 3, "year": year},
            ])

        schedule.sort(key=lambda x: x["date"])
        return schedule

    def get_schedule(self) -> List[Dict[str, str]]:
        """
        スケジュールを取得（キャッシュがあればキャッシュから）

        Returns:
            GDP発表スケジュールのリスト
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
                    return cached_data.get("schedule", [])
            except Exception as e:
                print(f"Error reading BEA schedule cache: {e}")

        # キャッシュがないか期限切れの場合、新規取得
        schedule = self.fetch_schedule_from_bea()
        self._save_cache(schedule)
        return schedule

    def _save_cache(self, schedule: List[Dict[str, str]]):
        """スケジュールをキャッシュに保存"""
        cache_path = self.CACHE_DIR / self.CACHE_FILE

        cache_data = {
            "schedule": schedule,
            "cached_at": datetime.now().isoformat(),
            "source": self.SCHEDULE_URL
        }

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    def get_upcoming_gdp_releases(self, count: int = 12) -> List[Dict[str, str]]:
        """
        今後のGDP発表日を取得

        Args:
            count: 取得する日付の数

        Returns:
            GDP発表日リスト（近い順）
        """
        schedule = self.get_schedule()
        today = date.today()

        upcoming = []
        for release in schedule:
            release_date = datetime.strptime(release["date"], "%Y-%m-%d").date()
            if release_date >= today:
                upcoming.append(release)
            if len(upcoming) >= count:
                break

        return upcoming

    def get_next_gdp_release(self) -> Optional[Dict[str, str]]:
        """
        次回のGDP発表を取得

        Returns:
            次回発表情報、またはNone
        """
        upcoming = self.get_upcoming_gdp_releases(count=1)
        return upcoming[0] if upcoming else None

    def get_last_gdp_release(self) -> Optional[Dict[str, str]]:
        """
        直近の過去GDP発表を取得（today より前で最も新しい発表）

        next_release は発表直後に未来日へ切り替わるため、
        stale 検出窓を見逃さないよう last_release もチェックする用途。

        Returns:
            直近の過去発表情報、またはNone
        """
        schedule = self.get_schedule()
        today = date.today()

        last_release = None
        for release in schedule:
            try:
                release_date = datetime.strptime(release["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError):
                continue
            if release_date < today:
                last_release = release
            else:
                break

        return last_release

    def get_release_datetime_jst(self, release_date_str: str) -> datetime:
        """
        発表日時を日本時間で取得

        Args:
            release_date_str: "YYYY-MM-DD"形式の日付

        Returns:
            日本時間の発表日時
        """
        release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

        # 米東部時間 8:30
        release_et = release_date.replace(
            hour=self.RELEASE_HOUR_ET,
            minute=self.RELEASE_MINUTE_ET,
            tzinfo=ET
        )

        # 日本時間に変換
        return release_et.astimezone(JST)

    def update_cache(self) -> bool:
        """
        キャッシュを強制的に更新

        Returns:
            成功したかどうか
        """
        try:
            schedule = self.fetch_schedule_from_bea()
            self._save_cache(schedule)
            return True
        except Exception as e:
            print(f"Error updating BEA schedule cache: {e}")
            return False

    def should_update_schedule(self) -> bool:
        """
        スケジュールを更新すべきかどうかを判定
        年2回（1月と7月の初旬）に更新を推奨

        Returns:
            更新が必要かどうか
        """
        now = datetime.now()

        # 1月または7月の1日〜15日の間は更新を推奨
        if now.month in [1, 7] and 1 <= now.day <= 15:
            cache_path = self.CACHE_DIR / self.CACHE_FILE

            if not cache_path.exists():
                return True

            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)

                cached_at = datetime.fromisoformat(cached_data.get("cached_at", "2000-01-01"))
                # 30日以上前のキャッシュなら更新
                return (datetime.now() - cached_at).days > 30
            except Exception:
                return True

        return False

    # =========================================================================
    # Personal Income and Outlays スケジュール
    # =========================================================================

    def fetch_personal_income_schedule_from_bea(self) -> List[Dict[str, str]]:
        """
        BEA公式ページからPersonal Income and Outlays発表スケジュールをスクレイピング

        Returns:
            Personal Income発表スケジュールのリスト
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(self.SCHEDULE_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            pi_releases = []

            # テーブルからスケジュールを抽出
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # 日付とタイトルを取得
                        date_text = cells[0].get_text(strip=True)
                        title_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""

                        # Personal Income and Outlaysに関連するエントリをフィルタ
                        if 'Personal Income' in title_text and 'Outlay' in title_text:
                            parsed_date = self._parse_date(date_text)
                            if parsed_date:
                                pi_releases.append({
                                    "date": parsed_date.strftime("%Y-%m-%d"),
                                    "date_str": date_text,
                                    "title": title_text,
                                    "target_month": self._extract_target_month(title_text, parsed_date),
                                    "type": "personal_income"
                                })

            # 日付でソート
            pi_releases.sort(key=lambda x: x["date"])

            if pi_releases:
                print(f"Fetched {len(pi_releases)} Personal Income releases from BEA")
                return pi_releases

            # スクレイピング失敗時はフォールバックを使用
            print("No Personal Income releases found via scraping, using fallback schedule")
            return self._get_personal_income_fallback_schedule()

        except Exception as e:
            print(f"Error fetching BEA Personal Income schedule: {e}")
            return self._get_personal_income_fallback_schedule()

    def _extract_target_month(self, title: str, release_date: date) -> str:
        """対象月を抽出"""
        # タイトルから月を抽出 (例: "November 2025")
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        for i, month in enumerate(months, 1):
            if month in title:
                # 年も抽出
                match = re.search(r'(20\d{2})', title)
                if match:
                    return f"{match.group(1)}-{i:02d}"
                # 年がない場合は発表月の前月を使用
                target_date = release_date.replace(day=1) - timedelta(days=1)
                return target_date.strftime("%Y-%m")

        # 抽出できない場合は発表月の前月
        target_date = release_date.replace(day=1) - timedelta(days=1)
        return target_date.strftime("%Y-%m")

    def _get_personal_income_fallback_schedule(self) -> List[Dict[str, str]]:
        """
        フォールバック用のPersonal Income発表スケジュール
        通常は毎月末（8:30 AM ET）に発表
        """
        current_year = datetime.now().year
        schedule = []

        # 2025年の実際のスケジュール（BEAから取得）
        pi_schedule_2025 = [
            ("2025-01-31", "January 31, 2025", "December 2024"),
            ("2025-02-28", "February 28, 2025", "January 2025"),
            ("2025-03-28", "March 28, 2025", "February 2025"),
            ("2025-04-30", "April 30, 2025", "March 2025"),
            ("2025-05-30", "May 30, 2025", "April 2025"),
            ("2025-06-27", "June 27, 2025", "May 2025"),
            ("2025-07-31", "July 31, 2025", "June 2025"),
            ("2025-08-29", "August 29, 2025", "July 2025"),
            ("2025-09-26", "September 26, 2025", "August 2025"),
            ("2025-10-31", "October 31, 2025", "September 2025"),
            ("2025-11-26", "November 26, 2025", "October 2025"),
            ("2025-12-23", "December 23, 2025", "November 2025"),
        ]

        for date_str, date_text, target_month in pi_schedule_2025:
            schedule.append({
                "date": date_str,
                "date_str": date_text,
                "title": f"Personal Income and Outlays, {target_month}",
                "target_month": target_month.replace(" ", "-"),
                "type": "personal_income"
            })

        # 2026年のスケジュールを生成（標準パターン）
        # Personal Income は前月分のデータを翌月末に発表
        # 例: December 2025 → January 30, 2026 発表
        pi_schedule_2026 = [
            ("2026-01-30", "January 30, 2026", "December 2025"),
            ("2026-02-27", "February 27, 2026", "January 2026"),
            ("2026-03-27", "March 27, 2026", "February 2026"),
            ("2026-04-30", "April 30, 2026", "March 2026"),
            ("2026-05-29", "May 29, 2026", "April 2026"),
            ("2026-06-26", "June 26, 2026", "May 2026"),
            ("2026-07-31", "July 31, 2026", "June 2026"),
            ("2026-08-28", "August 28, 2026", "July 2026"),
            ("2026-09-25", "September 25, 2026", "August 2026"),
            ("2026-10-30", "October 30, 2026", "September 2026"),
            ("2026-11-25", "November 25, 2026", "October 2026"),
            ("2026-12-23", "December 23, 2026", "November 2026"),
        ]

        for date_str, date_text, target_month in pi_schedule_2026:
            schedule.append({
                "date": date_str,
                "date_str": date_text,
                "title": f"Personal Income and Outlays, {target_month}",
                "target_month": target_month.replace(" ", "-"),
                "type": "personal_income"
            })

        schedule.sort(key=lambda x: x["date"])
        return schedule

    def get_personal_income_schedule(self) -> List[Dict[str, str]]:
        """
        Personal Incomeスケジュールを取得（キャッシュがあればキャッシュから）

        Returns:
            Personal Income発表スケジュールのリスト
        """
        cache_path = self.CACHE_DIR / self.PERSONAL_INCOME_CACHE_FILE

        # キャッシュを確認
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)

                # キャッシュの有効期限を確認
                cached_at = datetime.fromisoformat(cached_data.get("cached_at", "2000-01-01"))
                if (datetime.now() - cached_at).days < self.CACHE_EXPIRY_DAYS:
                    return cached_data.get("schedule", [])
            except Exception as e:
                print(f"Error reading Personal Income schedule cache: {e}")

        # キャッシュがないか期限切れの場合、新規取得
        schedule = self.fetch_personal_income_schedule_from_bea()
        self._save_personal_income_cache(schedule)
        return schedule

    def _save_personal_income_cache(self, schedule: List[Dict[str, str]]):
        """Personal Incomeスケジュールをキャッシュに保存"""
        cache_path = self.CACHE_DIR / self.PERSONAL_INCOME_CACHE_FILE

        cache_data = {
            "schedule": schedule,
            "cached_at": datetime.now().isoformat(),
            "source": self.SCHEDULE_URL
        }

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    def get_next_personal_income_release(self) -> Optional[Dict[str, str]]:
        """
        次回のPersonal Income発表を取得

        Returns:
            次回発表情報、またはNone
        """
        schedule = self.get_personal_income_schedule()
        today = date.today()

        for release in schedule:
            release_date = datetime.strptime(release["date"], "%Y-%m-%d").date()
            if release_date >= today:
                return release

        return None

    def get_personal_income_release_datetime_jst(self, release_date_str: str) -> datetime:
        """
        Personal Income発表日時を日本時間で取得

        Args:
            release_date_str: "YYYY-MM-DD"形式の日付

        Returns:
            日本時間の発表日時
        """
        release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

        # 米東部時間 8:30
        release_et = release_date.replace(
            hour=self.RELEASE_HOUR_ET,
            minute=self.RELEASE_MINUTE_ET,
            tzinfo=ET
        )

        # 日本時間に変換
        return release_et.astimezone(JST)


# グローバルインスタンス
bea_schedule_service = BEAScheduleService()
