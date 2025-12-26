"""
Challenger人員削減数サービス
Investing.comからChallenger Job Cutsデータを取得

指標:
- Challenger Job Cuts: 米国企業の人員削減発表数

データソース:
- https://sbcharts.investing.com/events_charts/us/888.json
- イベントID: 888 (Challenger Job Cuts)
- 発表元: Challenger, Gray & Christmas

発表スケジュール:
- Challenger公式カレンダーから取得
- https://www.challengergray.com/blog/{year}-challenger-report-release-calendar/
- 7:30 ET（米国東部時間）

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

# Investing.com JSONエンドポイント
INVESTING_CHALLENGER_URL = "https://sbcharts.investing.com/events_charts/us/888.json"

# Challenger公式カレンダーURL
CHALLENGER_CALENDAR_URL = "https://www.challengergray.com/blog/{year}-challenger-report-release-calendar/"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "challenger_job_cuts_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "challenger_schedule_cache.json"


class ChallengerJobCutsService:
    """Challenger人員削減数サービス"""

    DATA_CACHE_KEY = "investing:challenger_job_cuts:data"
    SCHEDULE_CACHE_KEY = "investing:challenger_job_cuts:schedule"

    # 発表時刻設定（ET）- 7:30 ET
    RELEASE_HOUR_ET = 7
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        pass

    def get_challenger_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Challenger人員削減数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "mom": float | null, "yoy": float | null}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
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

        # Investing.comからJSONで取得
        api_data = self._fetch_from_investing()

        if api_data:
            # 変化率を計算
            processed_data = self._calculate_changes(api_data)
            latest = processed_data[-1] if processed_data else None

            cache_payload = {
                "data": processed_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": processed_data,
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

    def _fetch_from_investing(self) -> List[Dict[str, Any]]:
        """Investing.comからChallenger人員削減数データを取得（JSON API）"""
        try:
            print("Fetching Challenger Job Cuts from Investing.com JSON API...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://jp.investing.com/"
            }

            response = requests.get(INVESTING_CHALLENGER_URL, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # dataからデータを抽出 [[timestamp, value, "No"], ...]
            data_list = data.get("data", [])
            if not data_list:
                print("No data found in response")
                return []

            result = []
            for item in data_list:
                if len(item) < 2:
                    continue

                timestamp = item[0]
                value = item[1]

                if timestamp is None or value is None:
                    continue

                try:
                    # タイムスタンプをミリ秒から日付に変換
                    dt = datetime.fromtimestamp(timestamp / 1000, tz=JST)
                    date_str = dt.strftime("%Y-%m-%d")

                    # 値は既に千人単位（k）なのでそのまま小数で保存
                    # 例: 71.321 = 71.321k = 71,321人
                    result.append({
                        "date": date_str,
                        "value": round(float(value), 3)
                    })
                except (ValueError, TypeError):
                    continue

            # 日付順にソート（古い順）
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} Challenger Job Cuts records from Investing.com")
            return result

        except Exception as e:
            print(f"Error fetching Challenger Job Cuts data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_target_month(self, announce_date: datetime) -> tuple:
        """
        発表日から対象月を計算

        Challenger Job Cutsは前月分を発表するが、発表日は通常月初旬
        - 月初旬（1-15日）に発表 → 前月分のデータ
        - 月後半（16-31日）に発表 → 当月分のデータ（稀なケース）

        例:
        - 2025-02-06 → 2025年1月分
        - 2024-10-31 → 2024年10月分（月末発表の場合は当月分）
        """
        if announce_date.day <= 15:
            # 月初旬の発表 → 前月分
            if announce_date.month == 1:
                return (announce_date.year - 1, 12)
            else:
                return (announce_date.year, announce_date.month - 1)
        else:
            # 月後半の発表 → 当月分
            return (announce_date.year, announce_date.month)

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        前月比と前年比を計算

        APIから取得した日付は実際の発表日（例: 2025-02-06 = 1月分のデータ）
        対象月ベースで比較するために、発表日から対象月を計算してインデックスを作成

        例: 2025-02-06（1月分）の前月比 = 12月分との比較
             2025-02-06（1月分）の前年比 = 2024年1月分との比較

        注: APIデータに同じ対象月のデータが複数ある場合（不規則な発表日）は
        最新の発表日のデータを使用
        """
        if not data:
            return []

        # 発表日を含めた対象月マップを作成
        # 同じ対象月に複数データがある場合は発表日が新しい方を採用
        month_map = {}  # key: (year, month), value: {"value": float, "announce_date": str}
        for item in data:
            dt = datetime.strptime(item["date"], "%Y-%m-%d")
            # 対象月を計算
            target_year, target_month = self._get_target_month(dt)
            key = (target_year, target_month)

            # 既存データより新しい発表日の場合のみ更新
            if key not in month_map or item["date"] > month_map[key]["announce_date"]:
                month_map[key] = {"value": item["value"], "announce_date": item["date"]}

        result = []
        for item in data:
            current_date = datetime.strptime(item["date"], "%Y-%m-%d")
            current_value = item["value"]

            # 対象月を計算
            target_year, target_month = self._get_target_month(current_date)

            # 前月比（MoM）を計算
            # 対象月の前月のキー
            if target_month == 1:
                prev_month_key = (target_year - 1, 12)
            else:
                prev_month_key = (target_year, target_month - 1)

            prev_month_data = month_map.get(prev_month_key)
            prev_month_value = prev_month_data["value"] if prev_month_data else None
            mom = None
            if prev_month_value and prev_month_value != 0:
                mom = round((current_value - prev_month_value) / prev_month_value * 100, 1)

            # 前年比（YoY）を計算
            # 対象月の前年同月のキー
            prev_year_key = (target_year - 1, target_month)
            prev_year_data = month_map.get(prev_year_key)
            prev_year_value = prev_year_data["value"] if prev_year_data else None
            yoy = None
            if prev_year_value and prev_year_value != 0:
                yoy = round((current_value - prev_year_value) / prev_year_value * 100, 1)

            result.append({
                "date": item["date"],
                "value": current_value,
                "mom": mom,
                "yoy": yoy
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
                    print(f"[Challenger] Release time passed: {release_jst}, last_updated: {last_updated}")
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得（公式カレンダーから）
        """
        try:
            # まずスケジュールキャッシュを確認
            schedule = self._get_release_schedule()
            if not schedule:
                # フォールバック: 計算方式
                return self._get_next_release_calculated()

            now = datetime.now(ET)
            today = now.date()

            # スケジュールから次回発表日を探す
            for release_date_str in schedule:
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()

                # 発表時刻を構築
                release_time = datetime(
                    release_date.year, release_date.month, release_date.day,
                    self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                    tzinfo=ET
                )

                # まだ発表時刻を過ぎていない場合
                if now < release_time:
                    return {
                        "date": release_date_str,
                        "label": f"Challenger Job Cuts - {release_date.strftime('%Y/%m/%d')} (木) 7:30 ET"
                    }

            # スケジュールに該当がない場合はフォールバック
            return self._get_next_release_calculated()

        except Exception as e:
            print(f"Error getting next release: {e}")
            return self._get_next_release_calculated()

    def _get_release_schedule(self) -> List[str]:
        """
        発表スケジュールを取得（キャッシュ付き）
        """
        # Redisキャッシュチェック
        cached_schedule = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached_schedule:
            cached_at = cached_schedule.get("cached_at")
            if cached_at:
                cached_time = datetime.fromisoformat(cached_at)
                # 24時間以内ならキャッシュを使用
                if datetime.now(JST) - cached_time < timedelta(hours=24):
                    return cached_schedule.get("dates", [])

        # ファイルキャッシュチェック
        file_cache = self._load_schedule_cache()
        if file_cache:
            cached_at = file_cache.get("cached_at")
            if cached_at:
                cached_time = datetime.fromisoformat(cached_at)
                # 24時間以内ならキャッシュを使用
                if datetime.now(JST) - cached_time < timedelta(hours=24):
                    redis_client.set(self.SCHEDULE_CACHE_KEY, file_cache, expire=86400)
                    return file_cache.get("dates", [])

        # 公式サイトからスクレイピング
        schedule = self._scrape_release_schedule()
        if schedule:
            cache_payload = {
                "dates": schedule,
                "cached_at": datetime.now(JST).isoformat()
            }
            redis_client.set(self.SCHEDULE_CACHE_KEY, cache_payload, expire=86400)
            self._save_schedule_cache(cache_payload)
            return schedule

        # スクレイピング失敗時はファイルキャッシュから返す
        if file_cache:
            return file_cache.get("dates", [])

        return []

    def _scrape_release_schedule(self) -> List[str]:
        """
        Challenger公式サイトから発表スケジュールをスクレイピング
        """
        try:
            now = datetime.now(ET)
            current_year = now.year
            all_dates = []

            # 今年と来年のスケジュールを取得
            for year in [current_year, current_year + 1]:
                url = CHALLENGER_CALENDAR_URL.format(year=year)
                print(f"Fetching Challenger schedule from: {url}")

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }

                try:
                    response = requests.get(url, headers=headers, timeout=15)
                    if response.status_code == 404:
                        print(f"Calendar page not found for {year}")
                        continue
                    response.raise_for_status()

                    soup = BeautifulSoup(response.text, 'html.parser')

                    # 日付パターンを探す（例: January 9, February 6, etc.）
                    # ページ内のリスト項目から日付を抽出
                    text = soup.get_text()

                    # 月名と日付のパターン
                    month_names = {
                        'January': 1, 'February': 2, 'March': 3, 'April': 4,
                        'May': 5, 'June': 6, 'July': 7, 'August': 8,
                        'September': 9, 'October': 10, 'November': 11, 'December': 12
                    }

                    # パターン: "Month Day" または "Month Day, Year"
                    pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,?\s*(\d{4}))?'
                    matches = re.findall(pattern, text)

                    for match in matches:
                        month_name, day, match_year = match
                        month = month_names[month_name]
                        day = int(day)

                        # 年が指定されていない場合は対象年を使用
                        if match_year:
                            target_year = int(match_year)
                        else:
                            target_year = year

                        try:
                            release_date = date(target_year, month, day)
                            date_str = release_date.strftime("%Y-%m-%d")
                            if date_str not in all_dates:
                                all_dates.append(date_str)
                        except ValueError:
                            continue

                except requests.RequestException as e:
                    print(f"Failed to fetch calendar for {year}: {e}")
                    continue

            # 日付順にソート
            all_dates.sort()
            print(f"Found {len(all_dates)} release dates from Challenger calendar")
            return all_dates

        except Exception as e:
            print(f"Error scraping release schedule: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_next_release_calculated(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を計算（フォールバック用）
        第1木曜日ベースの計算
        """
        try:
            now = datetime.now(ET)
            today = now.date()

            # 今月の第1木曜日を計算
            first_thursday_this_month = self._get_first_thursday_of_month(today.year, today.month)

            # 発表時刻
            release_time = datetime(
                first_thursday_this_month.year, first_thursday_this_month.month, first_thursday_this_month.day,
                self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                tzinfo=ET
            )

            # 今月の発表日時を過ぎていれば来月の第1木曜日
            if now >= release_time:
                if today.month == 12:
                    next_year = today.year + 1
                    next_month = 1
                else:
                    next_year = today.year
                    next_month = today.month + 1

                next_release_date = self._get_first_thursday_of_month(next_year, next_month)
            else:
                next_release_date = first_thursday_this_month

            return {
                "date": next_release_date.strftime("%Y-%m-%d"),
                "label": f"Challenger Job Cuts - {next_release_date.strftime('%Y/%m/%d')} (木) 7:30 ET (計算値)"
            }

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

    def _get_first_thursday_of_month(self, year: int, month: int) -> date:
        """
        指定した年月の第1木曜日を取得
        """
        first_day = date(year, month, 1)
        # 木曜日 = 3
        days_until_thursday = (3 - first_day.weekday()) % 7
        first_thursday = first_day + timedelta(days=days_until_thursday)
        return first_thursday

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
            print(f"Challenger Job Cuts cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def _load_schedule_cache(self) -> Optional[Dict[str, Any]]:
        """スケジュールキャッシュを読み込み"""
        try:
            if not SCHEDULE_CACHE_FILE.exists():
                return None
            with open(SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load schedule cache: {e}")
            return None

    def _save_schedule_cache(self, data: Dict[str, Any]) -> None:
        """スケジュールキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Challenger schedule cache saved to {SCHEDULE_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save schedule cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Challenger Job Cuts",
            "source": "Investing.com",
            "url": INVESTING_CHALLENGER_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
challenger_job_cuts_service = ChallengerJobCutsService()
