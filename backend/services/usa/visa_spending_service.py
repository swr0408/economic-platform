"""
Visa支出モメンタム指数サービス
FRED APIからVisa Spending Momentum Indexデータを取得

シリーズID:
- VISASMIHSA: Visa Spending Momentum Index (Seasonally Adjusted)

発表スケジュール:
- 毎月更新（具体的な発表日は不定）
- Visaサイトからスケジュールを取得（半年に1回程度更新）
- 発表日不明時: 1ヶ月経過後、新データがあるまで1日1回チェック

キャッシュ方式: 発表日時ベース判定方式
"""
import os
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
VISA_SMI_SERIES_ID = "VISASMIHSA"

# Visaリリーススケジュールページ
VISA_SMI_SCHEDULE_URL = "https://usa.visa.com/partner-with-us/visa-consulting-analytics/spending-momentum-index.html"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "visa_spending_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "visa_spending_schedule.json"


class VisaSpendingService:
    """Visa支出モメンタム指数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:series:visa_spending"
    SCHEDULE_CACHE_KEY = "visa:smi:schedule"

    # スケジュールキャッシュの有効期間（180日 = 約6ヶ月）
    SCHEDULE_CACHE_TTL = 180 * 24 * 60 * 60  # 15552000秒

    # データ更新チェック間隔（1日）
    DATA_CHECK_INTERVAL = 24 * 60 * 60  # 86400秒

    # 新データなし時の更新待機期間（30日 = 1ヶ月）
    NO_DATA_WAIT_PERIOD = 30  # 日数

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_visa_spending_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Visa支出モメンタム指数データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "mom": float, "yoy": float}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
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
                if last_updated_str and not self._should_refresh(last_updated_str, cached_data):
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
            file_cache = self._load_file_cache(DATA_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, file_cache):
                    data = file_cache.get("data", [])
                    next_release = self._get_next_release()

                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    return {
                        "data": data,
                        "latest": file_cache.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date)
        next_release = self._get_next_release()

        if api_data:
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（発表日時ベース判定方式）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(DATA_CACHE_FILE, cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(DATA_CACHE_FILE)
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

    def _fetch_from_api(
        self,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """FRED APIからVisa支出モメンタム指数データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching Visa Spending Momentum Index from FRED...")

            # デフォルト期間（2015年から）
            if not start_date:
                start_date = "2015-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": VISA_SMI_SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            raw_data = []
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        raw_data.append({
                            "date": obs["date"],
                            "value": round(float(obs["value"]), 2)
                        })
                    except (ValueError, TypeError):
                        continue

            # 前月比と前年比を計算
            result = []
            for i, item in enumerate(raw_data):
                entry = {
                    "date": item["date"],
                    "value": item["value"],
                    "mom": None,
                    "yoy": None
                }

                # 前月比（1ヶ月前のデータがあれば）
                if i >= 1:
                    prev_value = raw_data[i - 1]["value"]
                    if prev_value and prev_value != 0:
                        entry["mom"] = round(item["value"] - prev_value, 2)

                # 前年比（12ヶ月前のデータがあれば）
                if i >= 12:
                    year_ago_value = raw_data[i - 12]["value"]
                    if year_ago_value and year_ago_value != 0:
                        entry["yoy"] = round(item["value"] - year_ago_value, 2)

                result.append(entry)

            print(f"Fetched {len(result)} records from FRED (Visa Spending)")
            return result

        except Exception as e:
            print(f"Error fetching Visa Spending: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        1. 次回発表日がわかっている場合: 発表日を過ぎたら更新
        2. 次回発表日が不明の場合:
           - 最終更新から1ヶ月経過したら、1日1回APIをチェック
           - 新しいデータがあれば更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 次回発表情報を取得
            next_release = self._get_next_release()

            if next_release and next_release.get("date"):
                # 発表日時をパース
                release_date_str = next_release["date"]
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

                # 発表日を過ぎており、かつ最終更新が発表日より前なら更新が必要
                release_datetime = datetime(
                    release_date.year, release_date.month, release_date.day,
                    0, 0, 0, tzinfo=JST
                )

                if now >= release_datetime and last_updated < release_datetime:
                    return True

                return False

            else:
                # 発表日が不明の場合

                # 最終更新からの経過日数
                days_since_update = (now - last_updated).days

                # 1ヶ月（30日）以上経過していれば更新チェック
                if days_since_update >= self.NO_DATA_WAIT_PERIOD:
                    # 1日以上経過していれば更新
                    hours_since_update = (now - last_updated).total_seconds() / 3600
                    if hours_since_update >= 24:
                        return True

                return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得

        Visaサイトからスクレイピングして取得
        キャッシュがあればそれを使用（6ヶ月間有効）
        """
        # Redisキャッシュをチェック
        cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached:
            cached_at = cached.get("cached_at")
            if cached_at:
                try:
                    cached_dt = datetime.fromisoformat(cached_at)
                    if cached_dt.tzinfo is None:
                        cached_dt = cached_dt.replace(tzinfo=JST)
                    # キャッシュは6ヶ月間有効
                    if (datetime.now(JST) - cached_dt).total_seconds() < self.SCHEDULE_CACHE_TTL:
                        release_date_str = cached.get("date")
                        if release_date_str:
                            release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                            if release_date >= date.today():
                                return {
                                    "date": cached.get("date"),
                                    "label": cached.get("label")
                                }
                except Exception:
                    pass

        # ファイルキャッシュをチェック
        schedule_cache = self._load_file_cache(SCHEDULE_CACHE_FILE)
        if schedule_cache:
            cached_at = schedule_cache.get("cached_at")
            if cached_at:
                try:
                    cached_dt = datetime.fromisoformat(cached_at)
                    if cached_dt.tzinfo is None:
                        cached_dt = cached_dt.replace(tzinfo=JST)
                    if (datetime.now(JST) - cached_dt).total_seconds() < self.SCHEDULE_CACHE_TTL:
                        release_date_str = schedule_cache.get("date")
                        if release_date_str:
                            release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                            if release_date >= date.today():
                                # Redisにも保存
                                redis_client.set(self.SCHEDULE_CACHE_KEY, schedule_cache, expire=self.SCHEDULE_CACHE_TTL)
                                return {
                                    "date": schedule_cache.get("date"),
                                    "label": schedule_cache.get("label")
                                }
                except Exception:
                    pass

        # Visaサイトからスクレイピング
        scraped = self._scrape_next_release()
        if scraped:
            # キャッシュに保存（6ヶ月間有効）
            cache_data = {
                **scraped,
                "cached_at": datetime.now(JST).isoformat()
            }
            redis_client.set(self.SCHEDULE_CACHE_KEY, cache_data, expire=self.SCHEDULE_CACHE_TTL)
            self._save_file_cache(SCHEDULE_CACHE_FILE, cache_data)
            return scraped

        return None

    def _scrape_next_release(self) -> Optional[Dict[str, Any]]:
        """
        Visaサイトから次回発表日をスクレイピング

        発表スケジュールが見つからない場合はNoneを返す
        """
        try:
            print("Scraping next Visa SMI release date from Visa website...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(VISA_SMI_SCHEDULE_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # テキスト内容から日付を探す
            # "North American release date" セクションを探す
            today = date.today()

            # テーブルを探す
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    for cell in cells:
                        date_text = cell.get_text(strip=True)
                        parsed_date = self._parse_date_string(date_text)
                        if parsed_date and parsed_date >= today:
                            return {
                                "date": parsed_date.strftime("%Y-%m-%d"),
                                "label": f"Visa SMI - {parsed_date.strftime('%b %d, %Y')}"
                            }

            # テーブルが見つからない場合、リスト要素も確認
            for li in soup.find_all("li"):
                date_text = li.get_text(strip=True)
                parsed_date = self._parse_date_string(date_text)
                if parsed_date and parsed_date >= today:
                    return {
                        "date": parsed_date.strftime("%Y-%m-%d"),
                        "label": f"Visa SMI - {parsed_date.strftime('%b %d, %Y')}"
                    }

            print("Could not find next release date on Visa page")
            return None

        except Exception as e:
            print(f"Error scraping Visa page: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_date_string(self, date_str: str) -> Optional[date]:
        """日付文字列をパース"""
        date_str = date_str.strip()
        if not date_str or date_str.lower() in ["to be announced", "tba", "-"]:
            return None

        try:
            formats = [
                "%B %d, %Y",     # February 14, 2025
                "%b %d, %Y",     # Feb 14, 2025
                "%B %d %Y",      # February 14 2025
                "%b %d %Y",      # Feb 14 2025
                "%m/%d/%Y",      # 02/14/2025
                "%Y-%m-%d",      # 2025-02-14
                "%d %B %Y",      # 14 February 2025
                "%d %b %Y",      # 14 Feb 2025
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue

            # 時刻部分を除去して再試行
            import re
            date_str_clean = re.sub(r'\s*\([^)]*\)', '', date_str)
            date_str_clean = re.sub(r'\s+at\s+\d+.*$', '', date_str_clean)
            for fmt in formats:
                try:
                    return datetime.strptime(date_str_clean.strip(), fmt).date()
                except ValueError:
                    continue

        except Exception:
            pass

        return None

    def _load_file_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, cache_file: Path, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {cache_file}")
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
            "series_id": VISA_SMI_SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
visa_spending_service = VisaSpendingService()
