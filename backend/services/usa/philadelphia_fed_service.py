"""
フィラデルフィア連銀製造業景気指数（Philadelphia Fed Manufacturing Business Outlook Survey）サービス
FREDからデータを取得し、フィラデルフィア連銀サイトから発表スケジュールを半年ごとに取得

データソース:
- FRED: 10個のシリーズ（一般活動指数、新規受注、支払価格、従業員数、設備投資など）
- Philadelphia Fed Schedule: https://www.philadelphiafed.org/calendar-of-events

発表スケジュール:
- 毎月第3木曜日（8:30 ET = 22:30 JST 夏時間 / 23:30 JST 冬時間）
- フィラデルフィア連銀サイトから半年に一回スケジュールを取得してローカルに保存

キャッシュ方式: last_updated判定方式
- スケジュールファイルから次回発表日を取得して判定
- 発表日を過ぎたらキャッシュを無効化して再取得
"""
import json
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from bs4 import BeautifulSoup

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FRED API設定
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"

# FREDシリーズID（10個）
SERIES_IDS = {
    "general_activity_current": "GACDFSA066MSFRBPHI",     # 一般活動指数（現況）
    "general_activity_future": "GAFDFSA066MSFRBPHI",     # 一般活動指数（将来）
    "new_orders_current": "NOCDFSA066MSFRBPHI",          # 新規受注指数（現況）
    "new_orders_future": "NOFDFSA066MSFRBPHI",           # 新規受注指数（将来）
    "prices_paid_current": "PPCDFSA066MSFRBPHI",         # 支払価格指数（現況）
    "prices_paid_future": "PPFDFSA066MSFRBPHI",          # 支払価格指数（将来）
    "employment_current": "NECDFSA066MSFRBPHI",          # 従業員数指数（現況）
    "employment_future": "NEFDFSA066MSFRBPHI",           # 従業員数指数（将来）
    "capex_current": "CEBNDIF066MSFRBPHI",               # 設備投資指数（現況）
    "capex_future": "CEFDFSA066MSFRBPHI",                # 設備投資指数（将来）
}

# シリーズの表示設定
SERIES_CONFIG = {
    "general_activity_current": {"name": "一般活動指数", "color": "#1890ff", "group": "general"},
    "general_activity_future": {"name": "一般活動期待指数", "color": "#fa541c", "group": "general"},
    "new_orders_current": {"name": "新規受注指数", "color": "#52c41a", "group": "orders"},
    "new_orders_future": {"name": "新規受注期待指数", "color": "#faad14", "group": "orders"},
    "prices_paid_current": {"name": "支払価格指数", "color": "#722ed1", "group": "prices"},
    "prices_paid_future": {"name": "支払価格期待指数", "color": "#eb2f96", "group": "prices"},
    "employment_current": {"name": "従業員数指数", "color": "#13c2c2", "group": "employment"},
    "employment_future": {"name": "従業員数期待指数", "color": "#2f54eb", "group": "employment"},
    "capex_current": {"name": "設備投資指数", "color": "#a0d911", "group": "capex"},
    "capex_future": {"name": "設備投資期待指数", "color": "#ff7a45", "group": "capex"},
}

# スケジュールファイルパス
SCHEDULE_DIR = Path(__file__).parent.parent.parent / "schedules"
SCHEDULE_FILE = SCHEDULE_DIR / "philadelphia_fed_schedule.json"

# Philadelphia Fed スケジュールページURL
PHILLY_FED_SCHEDULE_URL = "https://www.philadelphiafed.org/calendar-of-events"


class PhiladelphiaFedService:
    """フィラデルフィア連銀製造業景気指数サービス"""

    CACHE_KEY = "fred:philadelphia_fed"
    SCHEDULE_CACHE_KEY = "schedule:philadelphia_fed"
    ECONALPHA_ID = "philadelphia_fed"  # FMPマッピング用ID

    def __init__(self):
        """初期化"""
        # スケジュールディレクトリの作成
        SCHEDULE_DIR.mkdir(parents=True, exist_ok=True)

    def get_philadelphia_fed_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        フィラデルフィア連銀製造業景気指数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", ...}, ...],
                "latest": {"date": "YYYY-MM-DD", ...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "series_config": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": get_next_release_from_fmp('philadelphia_fed'),
                        "series_config": SERIES_CONFIG,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # FREDからデータ取得
        fetched_result = self._fetch_from_fred()

        if fetched_result and fetched_result.get("data"):
            fetched_data = fetched_result["data"]

            # 日付でソート（昇順）
            fetched_data.sort(key=lambda x: x["date"])

            # 最新値を取得
            latest = fetched_data[-1] if fetched_data else None

            cache_payload = {
                "data": fetched_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            # last_updated方式: TTL=0（無期限、発表日判定で無効化）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": fetched_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp('philadelphia_fed'),
                "series_config": SERIES_CONFIG,
                "cached": False,
                "source": "fred",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('philadelphia_fed'),
            "series_config": SERIES_CONFIG,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _fetch_from_fred(self) -> Optional[Dict[str, Any]]:
        """FREDからPhiladelphia Fedデータを取得"""
        try:
            import os
            api_key = os.environ.get("FRED_API_KEY")
            if not api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Philadelphia Fed Manufacturing from FRED...")

            # 各シリーズを取得
            series_data = {}
            for name, series_id in SERIES_IDS.items():
                try:
                    params = {
                        "series_id": series_id,
                        "api_key": api_key,
                        "file_type": "json",
                        "sort_order": "asc",
                    }
                    response = requests.get(FRED_API_URL, params=params, timeout=30)
                    response.raise_for_status()
                    data = response.json()

                    observations = data.get("observations", [])
                    series_data[name] = {
                        obs["date"]: float(obs["value"])
                        for obs in observations
                        if obs.get("value") and obs["value"] != "."
                    }
                    print(f"  {name}: {len(series_data[name])} records")

                except Exception as e:
                    print(f"  Error fetching {name}: {e}")
                    continue

            if not series_data:
                return None

            # データを統合
            combined_data = self._combine_series_data(series_data)

            if combined_data:
                print(f"Combined {len(combined_data)} Philadelphia Fed records")
                return {"data": combined_data}

            return None

        except Exception as e:
            print(f"Error fetching Philadelphia Fed from FRED: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _combine_series_data(self, series_data: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """複数シリーズのデータを日付ごとに統合"""
        try:
            # 全日付を収集
            all_dates = set()
            for name, data in series_data.items():
                all_dates.update(data.keys())

            # 統合
            result = []
            for date_str in sorted(all_dates):
                item = {"date": date_str}

                # 各シリーズの値を追加
                for series_name in SERIES_IDS.keys():
                    if series_name in series_data and date_str in series_data[series_name]:
                        item[series_name] = round(series_data[series_name][date_str], 1)
                    else:
                        item[series_name] = None

                # 少なくとも一般活動指数（現況）があるレコードのみ追加
                if item.get("general_activity_current") is not None:
                    result.append(item)

            return result

        except Exception as e:
            print(f"Error combining series data: {e}")
            return []

    def _load_schedule(self) -> Optional[Dict[str, Any]]:
        """スケジュールファイルを読み込み"""
        try:
            if SCHEDULE_FILE.exists():
                with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"Error loading schedule: {e}")
            return None

    def _save_schedule(self, schedule: Dict[str, Any]) -> bool:
        """スケジュールファイルを保存"""
        try:
            schedule["updated_at"] = datetime.now(JST).isoformat()
            with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                json.dump(schedule, f, ensure_ascii=False, indent=2)
            print(f"Saved schedule to {SCHEDULE_FILE}")
            return True
        except Exception as e:
            print(f"Error saving schedule: {e}")
            return False

    def _is_schedule_stale(self, schedule: Optional[Dict[str, Any]]) -> bool:
        """
        スケジュールが古いかどうかを判定（6ヶ月以上経過）
        """
        if not schedule:
            return True

        updated_at = schedule.get("updated_at")
        if not updated_at:
            return True

        try:
            last_update = datetime.fromisoformat(updated_at)
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=JST)

            # 6ヶ月（約180日）以上経過していたら更新
            if datetime.now(JST) - last_update > timedelta(days=180):
                return True

            return False

        except Exception:
            return True

    def _scrape_schedule_from_philly_fed(self) -> Optional[Dict[str, Any]]:
        """フィラデルフィア連銀サイトから発表スケジュールをスクレイピング"""
        try:
            print("Scraping schedule from Philadelphia Fed...")

            # Manufacturing Business Outlook Surveyのリリースカレンダー
            url = f"{PHILLY_FED_SCHEDULE_URL}?release=manufacturing-business-outlook-survey#Economic-Release-Calendar"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            releases = []
            now = datetime.now()

            # イベントカレンダーから Manufacturing Business Outlook Survey を抽出
            # 複数のパターンで試行

            # パターン1: テーブル形式
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    row_text = row.get_text().lower()
                    if "manufacturing" in row_text and ("outlook" in row_text or "business" in row_text):
                        # 日付を探す
                        date_str = self._extract_date_from_text(row.get_text())
                        if date_str:
                            releases.append({
                                "date": date_str,
                                "label": "フィラデルフィア連銀製造業景気指数"
                            })

            # パターン2: リスト形式
            list_items = soup.find_all(["li", "div", "p"])
            for item in list_items:
                item_text = item.get_text().lower()
                if "manufacturing" in item_text and ("outlook" in item_text or "business" in item_text):
                    date_str = self._extract_date_from_text(item.get_text())
                    if date_str:
                        releases.append({
                            "date": date_str,
                            "label": "フィラデルフィア連銀製造業景気指数"
                        })

            # パターン3: 日付パターンを直接探す
            text = soup.get_text()
            # Manufacturing Business Outlook Survey の周辺テキストから日付抽出
            pattern = r"(?:Manufacturing\s+Business\s+Outlook|Business\s+Outlook\s+Survey).*?(\w+\s+\d{1,2},?\s+\d{4})"
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                date_str = self._parse_date_string(match)
                if date_str:
                    releases.append({
                        "date": date_str,
                        "label": "フィラデルフィア連銀製造業景気指数"
                    })

            # 重複を除去してソート
            seen = set()
            unique_releases = []
            for release in releases:
                if release["date"] not in seen:
                    seen.add(release["date"])
                    unique_releases.append(release)

            unique_releases.sort(key=lambda x: x["date"])

            # 現在日より後の日付のみフィルタ
            today = now.strftime("%Y-%m-%d")
            future_releases = [r for r in unique_releases if r["date"] >= today]

            if future_releases:
                print(f"Found {len(future_releases)} future release dates from Philadelphia Fed")
                return {
                    "releases": future_releases,
                    "source": "philadelphia_fed"
                }

            # スクレイピングが失敗した場合はデフォルトスケジュールを生成
            print("Could not scrape schedule, generating default...")
            return self._generate_default_schedule()

        except Exception as e:
            print(f"Error scraping schedule: {e}")
            import traceback
            traceback.print_exc()
            return self._generate_default_schedule()

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """テキストから日付を抽出"""
        # 複数のパターンを試行
        patterns = [
            r"(\w+)\s+(\d{1,2}),?\s+(\d{4})",  # January 15, 2025
            r"(\d{1,2})/(\d{1,2})/(\d{4})",     # 1/15/2025
            r"(\d{4})-(\d{2})-(\d{2})",         # 2025-01-15
        ]

        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    if len(match) == 3:
                        if match[0].isalpha():  # Month name format
                            month_name = match[0].lower()
                            if month_name in months:
                                month = months[month_name]
                                day = int(match[1])
                                year = int(match[2])
                                return f"{year:04d}-{month:02d}-{day:02d}"
                        elif len(match[2]) == 4:  # MM/DD/YYYY
                            month = int(match[0])
                            day = int(match[1])
                            year = int(match[2])
                            return f"{year:04d}-{month:02d}-{day:02d}"
                        elif len(match[0]) == 4:  # YYYY-MM-DD
                            return f"{match[0]}-{match[1]}-{match[2]}"
                except Exception:
                    continue

        return None

    def _parse_date_string(self, text: str) -> Optional[str]:
        """日付文字列をパース"""
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }

        text_lower = text.lower().strip()

        for month_name, month_num in months.items():
            if month_name in text_lower:
                # 日付を抽出
                day_match = re.search(rf"{month_name}\s+(\d{{1,2}})", text_lower)
                if day_match:
                    day = int(day_match.group(1))

                    # 年を抽出
                    year_match = re.search(r"(\d{4})", text)
                    if year_match:
                        year = int(year_match.group(1))
                        return f"{year:04d}-{month_num:02d}-{day:02d}"

        return None

    def _generate_default_schedule(self) -> Dict[str, Any]:
        """デフォルトの発表スケジュールを生成（毎月第3木曜日）"""
        releases = []
        now = datetime.now()

        # 今後12ヶ月分のスケジュールを生成
        for i in range(12):
            month = (now.month + i - 1) % 12 + 1
            year = now.year + (now.month + i - 1) // 12

            # 第3木曜日を計算
            first_day = datetime(year, month, 1)
            days_until_thursday = (3 - first_day.weekday()) % 7
            first_thursday = first_day.replace(day=1 + days_until_thursday)
            third_thursday = first_thursday.replace(day=first_thursday.day + 14)

            releases.append({
                "date": third_thursday.strftime("%Y-%m-%d"),
                "label": f"フィラデルフィア連銀製造業景気指数（{month}月発表）"
            })

        return {
            "releases": releases,
            "source": "generated"
        }

    def update_schedule(self) -> Dict[str, Any]:
        """発表スケジュールを手動更新"""
        schedule = self._scrape_schedule_from_philly_fed()
        if schedule:
            self._save_schedule(schedule)
            return {"success": True, "schedule": schedule}
        return {"success": False, "error": "Failed to update schedule"}

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None
        schedule = self._load_schedule()

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "schedule_updated_at": schedule.get("updated_at") if schedule else None,
            "schedule_source": schedule.get("source") if schedule else None
        }


# シングルトンインスタンス
philadelphia_fed_service = PhiladelphiaFedService()
