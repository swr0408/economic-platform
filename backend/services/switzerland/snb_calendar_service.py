"""
SNBカレンダーサービス（ICSインポート）
SNBのiCalendarフィードから発表スケジュールを取得

データソース:
1. SNB Website Calendar (自動取得可能):
   - URL: https://www.snb.ch/public/ical/calendar/en/{uuid}.ics
   - 参照: https://www.snb.ch/en/services-events/digital-services/rss-calendar-feeds
   - 内容: 金融政策発表、四半期報告、年次報告など

2. SNB Data Portal Calendar (手動ダウンロード必要):
   - URL: https://data.snb.ch/en/calendar
   - 内容: 月次銀行統計、金利・為替統計、四半期銀行統計など
   - 保存先: backend/data/ics_import/data_snb_ch_calendar_{year}.en.ics

カレンダーイベント例:
- "Monthly banking statistics, {Month} {Year}" → 月次銀行統計
- "Interest rates and exchange rates, {Month} {Year}" → 金利・為替
- "Quarterly banking statistics, Q{N} {Year}" → 四半期銀行統計
- "Monetary policy assessment" → 金融政策発表
- "Swiss balance of payments" → 国際収支
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ZURICH = ZoneInfo("Europe/Zurich")

# ICSファイル保存ディレクトリ
ICS_DIR = Path(__file__).parent.parent.parent / "data" / "ics_import"
ICS_DIR.mkdir(parents=True, exist_ok=True)

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "calendar"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SCHEDULE_CACHE_FILE = CACHE_DIR / "snb_schedule_cache.json"


class SNBCalendarService:
    """SNBカレンダーサービス（ICSベース）"""

    CACHE_KEY = "switzerland:snb_calendar:schedule"

    # SNB Website Calendar Feed URLs (自動取得可能)
    # これらは金融政策発表、四半期報告などを含む（銀行統計は含まない）
    SNB_WEBSITE_ICS_URLS = {
        2026: "https://www.snb.ch/public/ical/calendar/en/872f3023-70ea-42a9-8c27-524da3533fb7.ics",
        2027: "https://www.snb.ch/public/ical/calendar/en/ac3d067c-1b93-475e-9d22-56045798603d.ics",
    }

    # SNB Data Portal Calendar (手動ダウンロード必要)
    # https://data.snb.ch/en/calendar からダウンロードして保存
    # "Monthly banking statistics", "Interest rates and exchange rates" などを含む
    ICS_URLS = {}

    # Local ICS file patterns (manually downloaded from data.snb.ch)
    # Place files named like: snb_data_portal_calendar_2026.ics
    ICS_LOCAL_PATTERNS = [
        "snb_data_portal_calendar_{year}.ics",
        "data_snb_ch_calendar_{year}.en.ics",
        "snb_calendar_{year}.ics",
    ]

    # イベント名とカテゴリのマッピング
    # data.snb.ch形式のイベント（銀行統計関連）
    EVENT_CATEGORIES = {
        "Monthly banking statistics": "monthly_banking_statistics",
        "Interest rates and exchange rates": "interest_rates_exchange_rates",
        "Quarterly banking statistics": "quarterly_banking_statistics",
        "Economic data": "economic_data",
        "Exchange rate indices": "exchange_rate_indices",
        "Important monetary policy data": "monetary_policy_data",
        "SNB balance sheet items": "snb_balance_sheet",
        "Swiss balance of payments": "balance_of_payments",
        "Swiss Financial Accounts": "financial_accounts",
        "IMF SDDS Plus": "imf_sdds_plus",
        "Annual banking statistics": "annual_banking_statistics",
        "Selected data from the Quarterly Bulletin": "quarterly_bulletin",
    }

    # www.snb.ch形式のイベント（金融政策関連）
    WEBSITE_EVENT_CATEGORIES = {
        "Monetary policy assessment": "monetary_policy_decision",
        "Swiss balance of payments and Switzerland's international investment": "balance_of_payments",
        "Swiss Financial Accounts": "financial_accounts",
        "Quarterly Bulletin": "quarterly_bulletin",
        "Summary of monetary policy discussion": "monetary_policy_summary",
    }

    def __init__(self):
        self._schedule_cache: Optional[Dict[str, List[Dict]]] = None

    def get_next_release(self, category: str) -> Optional[str]:
        """指定カテゴリの次回発表日時を取得

        Args:
            category: カテゴリ名（EVENT_CATEGORIESの値）
                - "monthly_banking_statistics" → 月次銀行統計（M2, 住宅ローン残高等）
                - "interest_rates_exchange_rates" → 金利・為替統計
                - "quarterly_banking_statistics" → 四半期銀行統計（新規住宅ローン等）

        Returns:
            次回発表日時（"YYYY-MM-DD HH:MM"形式）またはNone
        """
        schedule = self._get_schedule()
        if not schedule or category not in schedule:
            return None

        now = datetime.now(ZURICH)
        events = schedule.get(category, [])

        for event in events:
            try:
                event_dt = datetime.strptime(event["datetime"], "%Y-%m-%d %H:%M")
                event_dt = event_dt.replace(tzinfo=ZURICH)
                if event_dt > now:
                    return event["datetime"]
            except (ValueError, KeyError):
                continue

        return None

    def get_all_next_releases(self) -> Dict[str, Optional[str]]:
        """全カテゴリの次回発表日時を取得"""
        result = {}
        all_categories = set(self.EVENT_CATEGORIES.values()) | set(self.WEBSITE_EVENT_CATEGORIES.values())
        for category in all_categories:
            result[category] = self.get_next_release(category)
        return result

    def _get_schedule(self) -> Dict[str, List[Dict]]:
        """スケジュールを取得（キャッシュ優先）"""
        # メモリキャッシュ
        if self._schedule_cache:
            return self._schedule_cache

        # Redisキャッシュ
        cached = redis_client.get(self.CACHE_KEY)
        if cached:
            self._schedule_cache = cached.get("schedule", {})
            return self._schedule_cache

        # ファイルキャッシュ
        file_cache = self._load_file_cache()
        if file_cache:
            self._schedule_cache = file_cache.get("schedule", {})
            redis_client.set(self.CACHE_KEY, file_cache, expire=0)
            return self._schedule_cache

        # ICSから取得
        return self.refresh_schedule()

    def refresh_schedule(self, force_download: bool = False) -> Dict[str, List[Dict]]:
        """ICSファイルからスケジュールを更新

        Args:
            force_download: Trueの場合、ICSファイルを再ダウンロード

        Returns:
            カテゴリ別のスケジュール辞書
        """
        all_events = []

        # 現在年と翌年のICSを取得
        current_year = datetime.now().year
        for year in [current_year, current_year + 1]:
            # 1. ローカルICSファイル（data.snb.ch形式 - 銀行統計）
            events = self._load_local_ics(year)
            all_events.extend(events)

            # 2. リモートICSファイル（www.snb.ch形式 - 金融政策）
            remote_events = self._load_remote_ics(year, force_download)
            all_events.extend(remote_events)

        # カテゴリ別に整理
        schedule = self._categorize_events(all_events)

        # キャッシュに保存
        cache_payload = {
            "schedule": schedule,
            "last_updated": datetime.now(JST).isoformat(),
        }
        self._schedule_cache = schedule
        redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return schedule

    def _load_local_ics(self, year: int) -> List[Dict]:
        """ローカルICSファイルを読み込み（data.snb.ch形式）

        Args:
            year: 年

        Returns:
            イベントリスト
        """
        # ローカルファイルを検索（複数のパターンをチェック）
        ics_file = None
        for pattern in self.ICS_LOCAL_PATTERNS:
            candidate = ICS_DIR / pattern.format(year=year)
            if candidate.exists():
                ics_file = candidate
                print(f"[SNBCalendar] Found local ICS: {ics_file}")
                break

        # ファイルが存在しない場合は空リスト
        if ics_file is None:
            print(f"[SNBCalendar] Local ICS file not found for year {year}")
            print(f"[SNBCalendar] Please download from https://data.snb.ch/en/calendar")
            print(f"[SNBCalendar] and save as one of: {[p.format(year=year) for p in self.ICS_LOCAL_PATTERNS]}")
            return []

        # ICSファイルをパース
        try:
            with open(ics_file, "r", encoding="utf-8") as f:
                ics_content = f.read()
            return self._parse_ics(ics_content)
        except Exception as e:
            print(f"[SNBCalendar] Error parsing local ICS file: {e}")
            return []

    def _load_remote_ics(self, year: int, force_download: bool = False) -> List[Dict]:
        """リモートICSファイルを取得（www.snb.ch形式）

        Args:
            year: 年
            force_download: 強制再ダウンロード

        Returns:
            イベントリスト
        """
        if year not in self.SNB_WEBSITE_ICS_URLS:
            return []

        cache_file = ICS_DIR / f"snb_website_calendar_{year}.ics"

        # キャッシュファイルが存在し、force_downloadでない場合はキャッシュを使用
        if cache_file.exists() and not force_download:
            # キャッシュが1日以内なら使用
            cache_age = datetime.now().timestamp() - cache_file.stat().st_mtime
            if cache_age < 86400:  # 24時間
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return self._parse_ics(f.read())
                except Exception:
                    pass  # フォールスルーしてダウンロード

        # リモートから取得
        try:
            url = self.SNB_WEBSITE_ICS_URLS[year]
            print(f"[SNBCalendar] Fetching remote ICS from: {url}")

            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            # キャッシュに保存
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(resp.text)
            print(f"[SNBCalendar] Cached remote ICS to: {cache_file}")

            return self._parse_ics(resp.text)

        except Exception as e:
            print(f"[SNBCalendar] Error fetching remote ICS: {e}")
            # フォールバック: キャッシュファイルがあれば使用
            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return self._parse_ics(f.read())
                except Exception:
                    pass
            return []

    def _parse_ics(self, ics_content: str) -> List[Dict]:
        """ICSコンテンツをパース

        Args:
            ics_content: ICSファイルの内容

        Returns:
            イベントリスト [{"summary": ..., "datetime": ..., "description": ...}, ...]
        """
        events = []
        current_event = {}
        in_event = False

        for line in ics_content.split('\n'):
            line = line.strip()

            if line == "BEGIN:VEVENT":
                in_event = True
                current_event = {}
            elif line == "END:VEVENT":
                if current_event:
                    # 日時をパース
                    dt_str = current_event.get("dtstart", "")
                    if dt_str:
                        parsed_dt = self._parse_ics_datetime(dt_str)
                        if parsed_dt:
                            current_event["datetime"] = parsed_dt
                            events.append(current_event)
                in_event = False
                current_event = {}
            elif in_event:
                if line.startswith("SUMMARY:"):
                    # バックスラッシュエスケープを処理
                    summary = line[8:].replace("\\,", ",").replace("\\n", "\n")
                    current_event["summary"] = summary
                elif line.startswith("DTSTART"):
                    # DTSTART;TZID=Europe/Zurich:20260121T090000
                    match = re.search(r':(\d{8}T\d{6})', line)
                    if match:
                        current_event["dtstart"] = match.group(1)
                elif line.startswith("DESCRIPTION:"):
                    current_event["description"] = line[12:]

        return events

    def _parse_ics_datetime(self, dt_str: str) -> Optional[str]:
        """ICS日時文字列をパース

        Args:
            dt_str: "20260121T090000" 形式

        Returns:
            "YYYY-MM-DD HH:MM" 形式
        """
        try:
            dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return None

    def _categorize_events(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """イベントをカテゴリ別に分類

        Args:
            events: パース済みイベントリスト

        Returns:
            カテゴリ別のイベント辞書
        """
        # 全カテゴリを初期化
        all_categories = set(self.EVENT_CATEGORIES.values()) | set(self.WEBSITE_EVENT_CATEGORIES.values())
        categorized = {cat: [] for cat in all_categories}

        for event in events:
            summary = event.get("summary", "")

            # data.snb.ch形式のイベントを検索
            matched = False
            for pattern, category in self.EVENT_CATEGORIES.items():
                if summary.startswith(pattern):
                    categorized[category].append({
                        "datetime": event.get("datetime"),
                        "summary": summary,
                    })
                    matched = True
                    break

            # www.snb.ch形式のイベントを検索
            if not matched:
                for pattern, category in self.WEBSITE_EVENT_CATEGORIES.items():
                    if pattern in summary:
                        categorized[category].append({
                            "datetime": event.get("datetime"),
                            "summary": summary,
                        })
                        break

        # 各カテゴリを日時でソート、重複を除去
        for category in categorized:
            # 日時でソート
            categorized[category].sort(key=lambda x: x.get("datetime", ""))
            # 重複除去（同じ日時のイベント）
            seen = set()
            unique_events = []
            for event in categorized[category]:
                key = event.get("datetime", "")
                if key not in seen:
                    seen.add(key)
                    unique_events.append(event)
            categorized[category] = unique_events

        return categorized

    def _load_file_cache(self) -> Optional[Dict]:
        """ファイルキャッシュを読み込む"""
        try:
            if not SCHEDULE_CACHE_FILE.exists():
                return None
            with open(SCHEDULE_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SNBCalendar] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SNBCalendar] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        self._schedule_cache = None
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        cached = redis_client.get(self.CACHE_KEY)
        all_categories = list(set(self.EVENT_CATEGORIES.values()) | set(self.WEBSITE_EVENT_CATEGORIES.values()))
        return {
            "indicator": "SNB Calendar",
            "source": "SNB iCalendar Feed (data.snb.ch + www.snb.ch)",
            "cache_key": self.CACHE_KEY,
            "exists": cached is not None,
            "last_updated": cached.get("last_updated") if cached else None,
            "categories": all_categories,
            "next_releases": self.get_all_next_releases() if cached else {},
            "file_cache_exists": SCHEDULE_CACHE_FILE.exists(),
            "ics_files": [f.name for f in ICS_DIR.glob("*.ics")],
            "remote_ics_urls": self.SNB_WEBSITE_ICS_URLS,
        }


# シングルトンインスタンス
snb_calendar_service = SNBCalendarService()


# ヘルパー関数
def get_snb_next_release(category: str) -> Optional[str]:
    """SNBカレンダーから次回発表日時を取得

    Args:
        category: カテゴリ名
            - "monthly_banking_statistics" → M2, 住宅ローン残高等
            - "interest_rates_exchange_rates" → 金利統計（住宅ローン金利含む）
            - "quarterly_banking_statistics" → 新規住宅ローン等

    Returns:
        次回発表日時（"YYYY-MM-DD HH:MM"形式）
    """
    return snb_calendar_service.get_next_release(category)
