"""
NER Pulse（週次雇用変動）サービス
ADP Media Centerから週次雇用変動データを取得

データソース:
- ADP Media Center: https://mediacenter.adp.com/labor-market-data
- プレスリリースからHTMLテーブルを直接解析

発表スケジュール:
- 毎週火曜日 8:15 AM ET（月次NER発表週を除く）
- 月次NERは毎月第1水曜日に発表されるため、その週の火曜日はNER Pulseなし

キャッシュ方式: 発表日時ベース判定方式
"""
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

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ner_pulse_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "ner_pulse_schedule.json"

# ADP Media CenterのURL
LABOR_MARKET_DATA_URL = "https://mediacenter.adp.com/labor-market-data"

# User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.7",
}


class NERPulseService:
    """NER Pulse（週次雇用変動）サービス"""

    DATA_CACHE_KEY = "adp:ner_pulse:data"
    SCHEDULE_CACHE_KEY = "adp:ner_pulse:schedule"

    # 発表時刻設定（ET）- 8:15 AM ET
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 15

    # 月名→月番号のマッピング
    MONTH_MAP = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12
    }

    def __init__(self):
        pass

    def get_ner_pulse_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        NER Pulseデータを取得

        Returns:
            {
                "data": [{"week_ending": str, "change": float}, ...],
                "latest": {...},
                "next_release": {"date": str, "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # 次回発表日を計算
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

        # Media Centerからスクレイピング
        scraped_result = self._scrape_ner_pulse()

        if scraped_result:
            scraped_data = scraped_result.get("data", [])
            scraped_next_release = scraped_result.get("next_release")
            latest = scraped_data[0] if scraped_data else None  # 最新が先頭

            # スクレイピングで取得した次回発表日を優先
            if scraped_next_release:
                next_release = scraped_next_release
                self._save_schedule_cache(next_release)

            cache_payload = {
                "data": scraped_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": scraped_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "scrape",
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

    def _scrape_ner_pulse(self) -> Optional[Dict[str, Any]]:
        """
        ADP Media Centerから最新のNER Pulseデータをスクレイピング

        Returns:
            {
                "data": [{"week_ending": "2025-12-06", "change": 11500}, ...],
                "next_release": {"date": "2026-01-13", "label": "..."} | None
            }
        """
        try:
            print("Scraping NER Pulse from Media Center...")

            # Step 1: Labor Market Dataページから最新プレスリリースURLを取得
            resp = requests.get(LABOR_MARKET_DATA_URL, headers=HEADERS, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # "Preliminary Estimate"を含むリンクを探す
            pr_link = None
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True)
                if 'Preliminary Estimate' in text:
                    pr_link = a['href']
                    break

            if not pr_link:
                print("No press release link found")
                return None

            print(f"Found press release: {pr_link}")

            # Step 2: プレスリリースページからテーブルと次回発表日を取得
            resp2 = requests.get(pr_link, headers=HEADERS, timeout=15)
            resp2.raise_for_status()

            soup2 = BeautifulSoup(resp2.text, 'html.parser')
            table = soup2.find('table')

            if not table:
                print("No table found in press release")
                return None

            # テーブルを解析
            data = []
            current_year = datetime.now().year

            for row in table.find_all('tr')[1:]:  # ヘッダーをスキップ
                cells = row.find_all('td')
                if len(cells) >= 2:
                    week_ending_raw = cells[0].get_text(strip=True)
                    change_raw = cells[1].get_text(strip=True).replace(',', '')

                    # 日付をパース (MM/DD/YY形式)
                    week_ending_date = self._parse_week_ending(week_ending_raw, current_year)
                    if week_ending_date is None:
                        continue

                    # 変化量をパース
                    try:
                        change = float(change_raw)
                    except ValueError:
                        continue

                    data.append({
                        "week_ending": week_ending_date,
                        "change": change  # 週次増減（人）
                    })

            print(f"Scraped {len(data)} NER Pulse records")

            # 次回発表日を抽出
            next_release = self._extract_next_release_from_text(resp2.text)

            return {
                "data": data,
                "next_release": next_release
            }

        except Exception as e:
            print(f"Error scraping NER Pulse: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_next_release_from_text(self, html_text: str) -> Optional[Dict[str, Any]]:
        """
        プレスリリースのテキストから次回発表日を抽出

        例: "The next NER Pulse will be released January 13, 2026"
        """
        try:
            # パターン: "next NER Pulse will be released [Month] [Day], [Year]"
            pattern = r'next NER Pulse will be released\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})'
            match = re.search(pattern, html_text, re.IGNORECASE)

            if match:
                month_name = match.group(1).lower()
                day = int(match.group(2))
                year = int(match.group(3))

                month = self.MONTH_MAP.get(month_name)
                if month:
                    date_str = f"{year:04d}-{month:02d}-{day:02d}"
                    label = f"NER Pulse - {year}/{month}/{day} 8:15 ET"
                    print(f"Found next release date from press release: {date_str}")
                    return {"date": date_str, "label": label}

            return None

        except Exception as e:
            print(f"Error extracting next release date: {e}")
            return None

    def _parse_week_ending(self, raw: str, current_year: int) -> Optional[str]:
        """
        日付文字列をYYYY-MM-DD形式に変換

        対応フォーマット:
        - MM/DD/YY (例: 12/6/25)
        - MM/DD/YYYY (例: 12/6/2025)
        """
        try:
            # MM/DD/YY or MM/DD/YYYY
            match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', raw)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                year = int(match.group(3))
                if year < 100:
                    year += 2000
                return f"{year:04d}-{month:02d}-{day:02d}"
            return None
        except Exception:
            return None

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
                    print(f"[NER Pulse] Release time passed: {release_jst}, last_updated: {last_updated}")
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得

        優先順位:
        1. スクレイピングで取得したキャッシュ（プレスリリースから抽出）
        2. 自動計算（毎週火曜日、月次NER発表週を除く）
        """
        try:
            today = date.today()

            # 1. キャッシュから取得（スクレイピングで取得した次回発表日）
            cached_schedule = self._load_schedule_cache()
            if cached_schedule:
                date_str = cached_schedule.get("date")
                if date_str:
                    try:
                        release_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        # 今日以降の日付であれば有効
                        if release_date >= today:
                            print(f"Using cached next release: {date_str}")
                            return cached_schedule
                    except ValueError:
                        pass

            # 2. 自動計算（フォールバック）
            return self._calculate_next_release()

        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を自動計算

        NER Pulseは毎週火曜日 8:15 ET発表
        ただし、月次NER発表週（第1水曜日を含む週）は除外
        """
        try:
            today = date.today()

            # 今週の火曜日を計算
            days_since_tuesday = (today.weekday() - 1) % 7  # 火曜日=1
            this_tuesday = today - timedelta(days=days_since_tuesday)

            # 次の火曜日候補を探す（今日を含む）
            candidate = this_tuesday
            if candidate < today:
                candidate += timedelta(days=7)

            # 4週間先までの火曜日をチェック
            for _ in range(4):
                # この週に月次NER発表（第1水曜日）があるかチェック
                week_wednesday = candidate + timedelta(days=1)  # 火曜日の翌日が水曜日

                # 第1水曜日かどうか
                if self._is_first_wednesday(week_wednesday):
                    # 月次NER発表週なのでスキップ
                    candidate += timedelta(days=7)
                    continue

                # 有効な発表日
                return {
                    "date": candidate.strftime("%Y-%m-%d"),
                    "label": f"NER Pulse - {candidate.strftime('%Y/%m/%d')} 8:15 ET (計算値)"
                }

            return None

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

    def _is_first_wednesday(self, d: date) -> bool:
        """その日付が月の第1水曜日かどうかを判定"""
        if d.weekday() != 2:  # 水曜日=2
            return False
        # 1日〜7日の間にあれば第1週
        return 1 <= d.day <= 7

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

    def _load_schedule_cache(self) -> Optional[Dict[str, Any]]:
        """次回発表日のスケジュールキャッシュを読み込み"""
        try:
            # まずRedisから取得
            cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
            if cached:
                return cached

            # Redisになければファイルから
            if not SCHEDULE_CACHE_FILE.exists():
                return None
            with open(SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Redisにも保存
                redis_client.set(self.SCHEDULE_CACHE_KEY, data, expire=0)
                return data
        except Exception as e:
            print(f"Failed to load schedule cache: {e}")
            return None

    def _save_schedule_cache(self, schedule: Dict[str, Any]) -> None:
        """次回発表日のスケジュールキャッシュを保存"""
        try:
            # Redisに保存
            redis_client.set(self.SCHEDULE_CACHE_KEY, schedule, expire=0)

            # ファイルにも保存
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(schedule, f, ensure_ascii=False, indent=2)
            print(f"NER Pulse schedule cache saved: {schedule}")
        except Exception as e:
            print(f"Failed to save schedule cache: {e}")

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"NER Pulse cache saved to {DATA_CACHE_FILE}")
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
            "indicator": "NER Pulse (Weekly Employment Change)",
            "source": "ADP Media Center",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ner_pulse_service = NERPulseService()
