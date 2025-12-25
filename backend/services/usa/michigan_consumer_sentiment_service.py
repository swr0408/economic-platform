"""
ミシガン大学消費者信頼感指数サービス
ミシガン大学 Survey of Consumers からデータを取得

指標:
- Index of Consumer Sentiment (ICS): 消費者信頼感指数

データソース:
- CSV: https://www.sca.isr.umich.edu/files/tbmics.csv
- 次回発表日: https://www.sca.isr.umich.edu/ からスクレイピング

発表スケジュール:
- 毎月2回発表（速報版・確報版）
- 速報版: 毎月第2金曜日 10:00 ET
- 確報版: 毎月最終金曜日 10:00 ET

キャッシュ方式: 発表日時ベース判定方式
"""
import csv
import io
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

# データソースURL
MICHIGAN_INDEX_CSV_URL = "https://www.sca.isr.umich.edu/files/tbmics.csv"
MICHIGAN_COMPONENTS_CSV_URL = "https://www.sca.isr.umich.edu/files/tbmiccice.csv"
MICHIGAN_HOMEPAGE_URL = "https://www.sca.isr.umich.edu/"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "michigan_consumer_sentiment_cache.json"

# 月名マッピング
MONTH_MAP = {
    'january': 1,
    'february': 2,
    'march': 3,
    'april': 4,
    'may': 5,
    'june': 6,
    'july': 7,
    'august': 8,
    'september': 9,
    'october': 10,
    'november': 11,
    'december': 12
}


class MichiganConsumerSentimentService:
    """ミシガン大学消費者信頼感指数サービス"""

    DATA_CACHE_KEY = "michigan:consumer_sentiment:data"

    # 発表時刻設定（ET）- 10:00 ET
    RELEASE_HOUR_ET = 10
    RELEASE_MINUTE_ET = 0

    def __init__(self):
        pass

    def get_michigan_consumer_sentiment_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ミシガン大学消費者信頼感指数データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "components": [{"date": "YYYY-MM-DD", "current": float, "expected": float}, ...],
                "latest": {...},
                "latest_components": {...},
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
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = self._get_next_release()
                    return {
                        "data": cached_data.get("data", []),
                        "components": cached_data.get("components", []),
                        "latest": cached_data.get("latest"),
                        "latest_components": cached_data.get("latest_components"),
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
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = self._get_next_release()

                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    return {
                        "data": file_cache.get("data", []),
                        "components": file_cache.get("components", []),
                        "latest": file_cache.get("latest"),
                        "latest_components": file_cache.get("latest_components"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # CSVからデータを取得（指数と構成要素の両方）
        index_data = self._fetch_index_from_csv()
        components_data = self._fetch_components_from_csv()
        next_release = self._get_next_release()

        if index_data:
            latest = index_data[-1] if index_data else None
            latest_components = components_data[-1] if components_data else None

            cache_payload = {
                "data": index_data,
                "components": components_data,
                "latest": latest,
                "latest_components": latest_components,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（発表日時ベース判定方式）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": index_data,
                "components": components_data,
                "latest": latest,
                "latest_components": latest_components,
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
                "components": file_cache.get("components", []),
                "latest": file_cache.get("latest"),
                "latest_components": file_cache.get("latest_components"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "components": [],
            "latest": None,
            "latest_components": None,
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_index_from_csv(self) -> List[Dict[str, Any]]:
        """ミシガン大学のCSVから指数データ（ICS_ALL）を取得"""
        try:
            print("Fetching Michigan Consumer Sentiment Index from CSV...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            response = requests.get(MICHIGAN_INDEX_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # CSVを読み込み（BOMを考慮）
            csv_text = response.content.decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(csv_text))

            result = []
            for row in reader:
                try:
                    month_str = row.get('Month', '').strip()
                    year_str = row.get('YYYY', '').strip()
                    value_str = row.get('ICS_ALL', '').strip()

                    if not month_str or not year_str or not value_str:
                        continue

                    # 日付を解析
                    date_obj = self._parse_month_year(month_str, year_str)
                    if not date_obj:
                        continue

                    # 値を解析
                    try:
                        value = float(value_str)
                    except ValueError:
                        continue

                    result.append({
                        "date": date_obj.strftime('%Y-%m-%d'),
                        "value": round(value, 1)
                    })

                except Exception as e:
                    print(f"Error processing index row: {e}")
                    continue

            # 日付順にソート（古い順）
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} Michigan Consumer Sentiment Index records")
            return result

        except Exception as e:
            print(f"Error fetching Michigan Consumer Sentiment Index data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_components_from_csv(self) -> List[Dict[str, Any]]:
        """ミシガン大学のCSVから構成要素データ（ICC/ICE）を取得"""
        try:
            print("Fetching Michigan Consumer Sentiment Components from CSV...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            response = requests.get(MICHIGAN_COMPONENTS_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # CSVを読み込み（BOMを考慮）
            csv_text = response.content.decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(csv_text))

            result = []
            for row in reader:
                try:
                    month_str = row.get('Month', '').strip()
                    year_str = row.get('YYYY', '').strip()
                    current_str = row.get('ICC', '').strip()
                    expected_str = row.get('ICE', '').strip()

                    if not month_str or not year_str or not current_str:
                        continue

                    # 日付を解析
                    date_obj = self._parse_month_year(month_str, year_str)
                    if not date_obj:
                        continue

                    # 値を解析
                    try:
                        current_value = float(current_str)
                    except ValueError:
                        continue

                    expected_value = None
                    if expected_str:
                        try:
                            expected_value = float(expected_str)
                        except ValueError:
                            pass

                    result.append({
                        "date": date_obj.strftime('%Y-%m-%d'),
                        "current": round(current_value, 1),
                        "expected": round(expected_value, 1) if expected_value is not None else None
                    })

                except Exception as e:
                    print(f"Error processing components row: {e}")
                    continue

            # 日付順にソート（古い順）
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} Michigan Consumer Sentiment Components records")
            return result

        except Exception as e:
            print(f"Error fetching Michigan Consumer Sentiment Components data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_month_year(self, month_str: str, year_str: str) -> Optional[datetime]:
        """月と年の文字列から日付オブジェクトを作成"""
        try:
            month_lower = month_str.lower()
            if month_lower not in MONTH_MAP:
                return None

            month_num = MONTH_MAP[month_lower]
            year_num = int(float(year_str))

            return datetime(year_num, month_num, 1)

        except Exception as e:
            print(f"Error parsing date {month_str} {year_str}: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - 次回発表日時を過ぎており、かつ最終更新が発表日時より前なら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 次回発表日時を取得
            next_release = self._get_next_release()

            if next_release and next_release.get("date"):
                # 発表日時をパース
                release_date_str = next_release["date"]
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

                # 発表時刻（10:00 ET）をJSTに変換
                release_et = datetime(
                    release_date.year, release_date.month, release_date.day,
                    self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                    tzinfo=ET
                )
                release_jst = release_et.astimezone(JST)

                # 発表日時を過ぎており、かつ最終更新が発表日時より前なら更新が必要
                if now >= release_jst and last_updated < release_jst:
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得

        ミシガン大学のホームページからスクレイピングで取得
        フォーマット: "Friday, January 09, 2026 for Preliminary January data at 10am ET"
        """
        try:
            # まずキャッシュされた発表日をチェック
            cached_release = self._get_cached_next_release()
            if cached_release:
                # キャッシュされた発表日が未来なら使用
                release_date = datetime.strptime(cached_release["date"], "%Y-%m-%d").date()
                if release_date >= date.today():
                    return cached_release

            # ホームページからスクレイピング
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            response = requests.get(MICHIGAN_HOMEPAGE_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # "Next data release:" を探す
            text = soup.get_text()

            # パターン: "Next data release: Friday, January 09, 2026 for Preliminary January data at 10am ET"
            pattern = r'Next data release:\s*(\w+),\s*(\w+)\s+(\d{1,2}),\s*(\d{4})'
            match = re.search(pattern, text)

            if match:
                day_of_week = match.group(1)
                month_name = match.group(2)
                day = int(match.group(3))
                year = int(match.group(4))

                month_num = MONTH_MAP.get(month_name.lower())
                if month_num:
                    release_date = date(year, month_num, day)

                    # 速報版か確報版かを判定
                    is_preliminary = 'preliminary' in text.lower()
                    release_type = "速報版" if is_preliminary else "確報版"

                    result = {
                        "date": release_date.strftime("%Y-%m-%d"),
                        "label": f"Michigan Consumer Sentiment ({release_type}) - {release_date.strftime('%Y/%m/%d')} ({day_of_week[:3]}) 10:00 ET"
                    }

                    # キャッシュに保存
                    self._save_next_release_cache(result)

                    return result

            # スクレイピング失敗時はフォールバック計算
            return self._calculate_next_release_fallback()

        except Exception as e:
            print(f"Error getting next release: {e}")
            return self._calculate_next_release_fallback()

    def _calculate_next_release_fallback(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日のフォールバック計算

        ミシガン大学消費者信頼感は毎月2回発表:
        - 速報版: 第2金曜日
        - 確報版: 最終金曜日
        """
        try:
            now = datetime.now(ET)
            today = now.date()

            # 今月の第2金曜日と最終金曜日を計算
            second_friday = self._get_nth_weekday_of_month(today.year, today.month, 4, 2)  # 金曜日=4, 2回目
            last_friday = self._get_last_weekday_of_month(today.year, today.month, 4)  # 金曜日=4

            # 発表時刻
            second_friday_time = datetime(
                second_friday.year, second_friday.month, second_friday.day,
                self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            last_friday_time = datetime(
                last_friday.year, last_friday.month, last_friday.day,
                self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                tzinfo=ET
            )

            # 次回発表日を決定
            if now < second_friday_time:
                next_release_date = second_friday
                release_type = "速報版"
            elif now < last_friday_time:
                next_release_date = last_friday
                release_type = "確報版"
            else:
                # 来月の第2金曜日
                if today.month == 12:
                    next_year = today.year + 1
                    next_month = 1
                else:
                    next_year = today.year
                    next_month = today.month + 1

                next_release_date = self._get_nth_weekday_of_month(next_year, next_month, 4, 2)
                release_type = "速報版"

            return {
                "date": next_release_date.strftime("%Y-%m-%d"),
                "label": f"Michigan Consumer Sentiment ({release_type}) - {next_release_date.strftime('%Y/%m/%d')} (金) 10:00 ET"
            }

        except Exception as e:
            print(f"Error calculating fallback next release: {e}")
            return None

    def _get_nth_weekday_of_month(self, year: int, month: int, weekday: int, n: int) -> date:
        """
        指定した年月のn回目の曜日を取得

        Args:
            year: 年
            month: 月
            weekday: 曜日（0=月曜日, 4=金曜日）
            n: 何回目か（1, 2, 3...）

        Returns:
            n回目の曜日の日付
        """
        first_day = date(year, month, 1)
        first_weekday = first_day.weekday()

        # 最初の指定曜日までの日数
        days_until_weekday = (weekday - first_weekday) % 7
        first_target = first_day + timedelta(days=days_until_weekday)

        # n回目
        return first_target + timedelta(weeks=n - 1)

    def _get_last_weekday_of_month(self, year: int, month: int, weekday: int) -> date:
        """
        指定した年月の最終の曜日を取得

        Args:
            year: 年
            month: 月
            weekday: 曜日（0=月曜日, 4=金曜日）

        Returns:
            最終の曜日の日付
        """
        # 月末を計算
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)

        last_day = next_month - timedelta(days=1)

        # 最終の指定曜日を探す
        days_since_weekday = (last_day.weekday() - weekday) % 7
        return last_day - timedelta(days=days_since_weekday)

    def _get_cached_next_release(self) -> Optional[Dict[str, Any]]:
        """キャッシュされた次回発表日を取得"""
        try:
            cache_file = CACHE_DIR / "michigan_next_release_cache.json"
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _save_next_release_cache(self, data: Dict[str, Any]) -> None:
        """次回発表日をキャッシュに保存"""
        try:
            cache_file = CACHE_DIR / "michigan_next_release_cache.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save next release cache: {e}")

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
            print(f"Cache saved to {DATA_CACHE_FILE}")
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
            "indicator": "Michigan Consumer Sentiment Index",
            "source": "University of Michigan Survey of Consumers",
            "url": MICHIGAN_CSV_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
michigan_consumer_sentiment_service = MichiganConsumerSentimentService()
