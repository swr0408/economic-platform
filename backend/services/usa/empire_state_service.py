"""
NY連銀製造業景気指数（Empire State Manufacturing Survey）サービス
FREDからデータを取得し、NY連銀サイトから発表スケジュールを半年ごとに取得

データソース:
- FRED: GACDISA066MSFRBNY（現況指数）、GAFDISA066MSFRBNY（期待指数）
- NY Fed Schedule: https://www.newyorkfed.org/survey/empire/empiresurvey_overview

発表スケジュール:
- 毎月15日付近（8:30 ET = 22:30 JST 夏時間 / 23:30 JST 冬時間）
- NY連銀サイトから半年に一回スケジュールを取得してローカルに保存

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


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FRED API設定
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"

# FREDシリーズID
SERIES_IDS = {
    "current": "GACDISA066MSFRBNY",  # 現況指数（General Business Conditions - Current）
    "future": "GAFDISA066MSFRBNY",   # 期待指数（General Business Conditions - Future）
}

# スケジュールファイルパス
SCHEDULE_DIR = Path(__file__).parent.parent.parent / "schedules"
SCHEDULE_FILE = SCHEDULE_DIR / "empire_state_schedule.json"

# NY Fed スケジュールページURL
NYFED_SCHEDULE_URL = "https://www.newyorkfed.org/survey/empire/empiresurvey_overview"


class EmpireStateService:
    """NY連銀製造業景気指数サービス"""

    CACHE_KEY = "fred:empire_state"
    SCHEDULE_CACHE_KEY = "schedule:empire_state"

    def __init__(self):
        """初期化"""
        # スケジュールディレクトリの作成
        SCHEDULE_DIR.mkdir(parents=True, exist_ok=True)

    def get_empire_state_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        NY連銀製造業景気指数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "current": float, "future": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "current": float, "future": float},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
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
                    # 次回発表日を動的に取得
                    next_release = self._get_next_release()
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
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

            # 次回発表日を取得
            next_release = self._get_next_release()

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
                "next_release": next_release,
                "cached": False,
                "source": "fred",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        Empire State Manufacturing Surveyの発表スケジュール:
        - 発表日: 毎月15日付近（12日〜18日の範囲）
        - 発表時刻: 8:30 ET = 22:30 JST（夏時間）/ 23:30 JST（冬時間）

        判定ロジック:
        - 発表期間内（12日〜18日）で、最終更新が今月の発表期間開始より前なら更新必要

        Args:
            last_updated_str: 最終更新日時のISO文字列

        Returns:
            True: 更新が必要
            False: キャッシュ有効
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 発表期間: 毎月12日〜18日（15日付近）
            if 12 <= now.day <= 18:
                # 今月の発表期間開始日時（12日 22:00 JST）
                release_window_start = now.replace(day=12, hour=22, minute=0, second=0, microsecond=0)

                # 最終更新が今月の発表期間開始より前なら更新必要
                if last_updated < release_window_start:
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _fetch_from_fred(self) -> Optional[Dict[str, Any]]:
        """FREDからEmpire Stateデータを取得"""
        try:
            import os
            api_key = os.environ.get("FRED_API_KEY")
            if not api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Empire State Manufacturing from FRED...")

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
                print(f"Combined {len(combined_data)} Empire State records")
                return {"data": combined_data}

            return None

        except Exception as e:
            print(f"Error fetching Empire State from FRED: {e}")
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

                # 現況指数
                if "current" in series_data and date_str in series_data["current"]:
                    item["current"] = round(series_data["current"][date_str], 1)
                else:
                    item["current"] = None

                # 期待指数
                if "future" in series_data and date_str in series_data["future"]:
                    item["future"] = round(series_data["future"][date_str], 1)
                else:
                    item["future"] = None

                # 少なくとも現況指数があるレコードのみ追加
                if item.get("current") is not None:
                    result.append(item)

            return result

        except Exception as e:
            print(f"Error combining series data: {e}")
            return []

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        """
        次回発表日を取得

        1. スケジュールファイルから取得
        2. ファイルが古い（6ヶ月以上）場合はNY Fedからスクレイピングして更新
        """
        try:
            schedule = self._load_schedule()

            # スケジュールが古い場合は更新
            if self._is_schedule_stale(schedule):
                print("Schedule is stale, updating from NY Fed...")
                new_schedule = self._scrape_schedule_from_nyfed()
                if new_schedule and new_schedule.get("releases"):
                    self._save_schedule(new_schedule)
                    schedule = new_schedule

            if not schedule or not schedule.get("releases"):
                return None

            # 現在日時より後の次回発表日を探す
            now = datetime.now(JST).date()
            for release in schedule["releases"]:
                try:
                    release_date = datetime.strptime(release["date"], "%Y-%m-%d").date()
                    if release_date >= now:
                        return {
                            "date": release["date"],
                            "label": release.get("label", f"NY連銀製造業景気指数（{release_date.month}月発表）")
                        }
                except Exception:
                    continue

            return None

        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

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

    def _scrape_schedule_from_nyfed(self) -> Optional[Dict[str, Any]]:
        """NY連銀サイトから発表スケジュールをスクレイピング"""
        try:
            print(f"Scraping schedule from NY Fed...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(NYFED_SCHEDULE_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # 発表スケジュールを探す
            releases = []
            now = datetime.now()

            # テーブルからスケジュールを抽出（2025, 2026のカラムを探す）
            tables = soup.find_all("table")
            for table in tables:
                # 年を特定するためにヘッダーをチェック
                headers_row = table.find("tr")
                if not headers_row:
                    continue

                # テーブル全体のテキストから年と月日を抽出
                table_text = table.get_text()

                # 年ごとに日付を探す（2025, 2026）
                for year in [2025, 2026]:
                    if str(year) in table_text:
                        # 各月の日付パターンを探す
                        for month_name, month_num in [
                            ("January", 1), ("February", 2), ("March", 3), ("April", 4),
                            ("May", 5), ("June", 6), ("July", 7), ("August", 8),
                            ("September", 9), ("October", 10), ("November", 11), ("December", 12)
                        ]:
                            # "月名 日" のパターンを探す
                            pattern = rf"{month_name}\s+(\d{{1,2}})"
                            matches = re.findall(pattern, table_text)
                            if matches:
                                # 最初のマッチを使用
                                day = int(matches[0])
                                date_str = f"{year}-{month_num:02d}-{day:02d}"
                                releases.append({
                                    "date": date_str,
                                    "label": f"NY連銀製造業景気指数（{year}年{month_num}月）"
                                })

            # 重複を除去してソート
            seen = set()
            unique_releases = []
            for release in releases:
                if release["date"] not in seen:
                    seen.add(release["date"])
                    unique_releases.append(release)

            unique_releases.sort(key=lambda x: x["date"])

            # 現在日より後の日付のみフィルタ（過去を除外）
            today = now.strftime("%Y-%m-%d")
            future_releases = [r for r in unique_releases if r["date"] >= today]

            if future_releases:
                print(f"Found {len(future_releases)} future release dates")
                return {
                    "releases": future_releases,
                    "source": "ny_fed"
                }

            # スクレイピングが失敗した場合はデフォルトスケジュールを生成
            print("Could not scrape schedule, generating default...")
            return self._generate_default_schedule()

        except Exception as e:
            print(f"Error scraping schedule: {e}")
            return self._generate_default_schedule()

    def _parse_schedule_date(self, text: str) -> Optional[str]:
        """スケジュール日付テキストをパース"""
        try:
            # パターン: "January 15, 2025" or "January 15"
            months = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12
            }

            text_lower = text.lower()

            for month_name, month_num in months.items():
                if month_name in text_lower:
                    # 日付を抽出
                    day_match = re.search(rf"{month_name}\s+(\d{{1,2}})", text_lower)
                    if day_match:
                        day = int(day_match.group(1))

                        # 年を抽出（なければ現在または次の年）
                        year_match = re.search(r"(\d{4})", text)
                        if year_match:
                            year = int(year_match.group(1))
                        else:
                            now = datetime.now()
                            year = now.year
                            # 過去の日付なら来年と判断
                            if month_num < now.month or (month_num == now.month and day < now.day):
                                year += 1

                        return f"{year:04d}-{month_num:02d}-{day:02d}"

            return None

        except Exception:
            return None

    def _generate_default_schedule(self) -> Dict[str, Any]:
        """デフォルトの発表スケジュールを生成（毎月15日）"""
        releases = []
        now = datetime.now()

        # 今後12ヶ月分のスケジュールを生成
        for i in range(12):
            month = (now.month + i - 1) % 12 + 1
            year = now.year + (now.month + i - 1) // 12

            # 15日（土日なら翌週月曜、または直前金曜に調整）
            release_date = datetime(year, month, 15)

            # 土曜日なら17日（月曜）、日曜なら16日（月曜）に調整
            if release_date.weekday() == 5:  # 土曜
                release_date = release_date.replace(day=17)
            elif release_date.weekday() == 6:  # 日曜
                release_date = release_date.replace(day=16)

            releases.append({
                "date": release_date.strftime("%Y-%m-%d"),
                "label": f"NY連銀製造業景気指数（{month}月発表）"
            })

        return {
            "releases": releases,
            "source": "generated"
        }

    def update_schedule(self) -> Dict[str, Any]:
        """発表スケジュールを手動更新"""
        schedule = self._scrape_schedule_from_nyfed()
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
            "next_release": self._get_next_release(),
            "schedule_updated_at": schedule.get("updated_at") if schedule else None,
            "schedule_source": schedule.get("source") if schedule else None
        }


# シングルトンインスタンス
empire_state_service = EmpireStateService()
