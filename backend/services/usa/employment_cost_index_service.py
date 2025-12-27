"""
雇用コスト指数（Employment Cost Index）サービス
FRED APIからECIALLCIV（Total Compensation）データを取得

指標:
- ECIALLCIV: Employment Cost Index: Total Compensation: All Civilian Workers

データソース:
- FRED: https://fred.stlouisfed.org/series/ECIALLCIV
- Investing.com: https://www.investing.com/economic-calendar/employment-cost-index-331

発表スケジュール:
- BLS Employment Cost Index
- 四半期ごと発表（1月、4月、7月、10月）
- 8:30 AM ET
- Investing.comから次回発表日を自動取得（取得失敗時はブランク表示）

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import re
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
ECIALLCIV_SERIES_ID = "ECIALLCIV"  # Employment Cost Index: Total Compensation

# Investing.com ECI 経済カレンダーURL
INVESTING_ECI_URL = "https://www.investing.com/economic-calendar/employment-cost-index-331"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "employment_cost_index_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "eci_schedule.json"

# 月名マッピング
MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9,
    'oct': 10, 'nov': 11, 'dec': 12
}


class EmploymentCostIndexService:
    """雇用コスト指数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:employment_cost_index:data"
    SCHEDULE_CACHE_KEY = "bls:eci:schedule"

    # 発表時刻設定（ET）- 8:30 AM ET
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_employment_cost_index_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        雇用コスト指数データを取得（前期比）

        Returns:
            {
                "data": [{"date": str, "value": float, "pch": float}, ...],
                "latest": {...},
                "next_release": {"date": str, "label": str} | null,
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
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = self._get_next_release()
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)
        next_release = self._get_next_release()

        if api_data:
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
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

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから雇用コスト指数データを取得（前期比 = pch）"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Employment Cost Index (pch) from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 前期比 (units=pch) で取得
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": ECIALLCIV_SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc",
                "units": "pch"  # 前期比
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            observations = data.get("observations", [])

            result = []
            for obs in observations:
                try:
                    value_str = obs.get("value", "")
                    if value_str == "." or not value_str:
                        continue
                    pch = float(value_str)
                    result.append({
                        "date": obs["date"],
                        "pch": round(pch, 2)  # 前期比（%）
                    })
                except (ValueError, KeyError):
                    continue

            print(f"Fetched {len(result)} Employment Cost Index records")
            return result

        except Exception as e:
            print(f"Error fetching Employment Cost Index: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            next_release = self._get_next_release()

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
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得（Investing.comからスクレイピング）

        スクレイピングタイミング:
        - 発表日から2ヶ月（60日）経過後に初回チェック
        - その後は3日おきにチェック
        - 次回発表日が見つかればキャッシュして返す
        """
        try:
            today = date.today()

            # キャッシュチェック
            cached_schedule = self._get_cached_schedule()
            if cached_schedule:
                # 次回発表日を探す（今日以降の日付があればそれを返す）
                for release in cached_schedule.get("releases", []):
                    release_date_str = release.get("date")
                    if release_date_str:
                        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                        if release_date >= today:
                            return release

                # キャッシュ内の日付がすべて過去 → 再取得が必要かチェック
                if not self._should_scrape_schedule(cached_schedule):
                    # まだスクレイピング時期ではない
                    return None

            # Investing.comからスクレイピング
            next_release = self._fetch_investing_schedule()
            if next_release:
                # キャッシュに保存
                self._save_schedule_cache({"releases": [next_release]})
                return next_release

            # 取得失敗時もキャッシュに記録（再スクレイピング防止）
            self._save_schedule_cache({"releases": [], "fetch_failed": True})
            return None

        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

    def _should_scrape_schedule(self, cached_schedule: Dict[str, Any]) -> bool:
        """
        スクレイピングすべきタイミングかを判定

        ロジック:
        1. 最後の発表日（データの最新日付）から2ヶ月（60日）経過していなければスクレイピングしない
        2. 2ヶ月経過後は3日（72時間）おきにチェック
        """
        try:
            now = datetime.now(JST)

            # 最後の発表日を取得（データキャッシュから）
            last_release_date = self._get_last_release_date()

            if last_release_date:
                days_since_release = (now.date() - last_release_date).days

                # 発表日から60日（約2ヶ月）経過していなければスクレイピングしない
                if days_since_release < 60:
                    print(f"ECI: Only {days_since_release} days since last release, waiting until 60 days")
                    return False

            # 2ヶ月経過後: 前回スクレイピングから3日（72時間）経過しているかチェック
            cached_at = cached_schedule.get("cached_at")
            if cached_at:
                try:
                    cached_dt = datetime.fromisoformat(cached_at)
                    if cached_dt.tzinfo is None:
                        cached_dt = cached_dt.replace(tzinfo=JST)
                    hours_since_cache = (now - cached_dt).total_seconds() / 3600

                    # 72時間（3日）以内にスクレイピング済みならスキップ
                    if hours_since_cache < 72:
                        print(f"ECI: Last scraped {hours_since_cache:.1f} hours ago, waiting until 72 hours")
                        return False
                except Exception:
                    pass

            # スクレイピング実行
            print(f"ECI: Ready to scrape schedule (>60 days since release, >72 hours since last scrape)")
            return True

        except Exception as e:
            print(f"Error checking scrape timing: {e}")
            return True  # エラー時はスクレイピングを試行

    def _get_last_release_date(self) -> Optional[date]:
        """データキャッシュから最後の発表日（最新データの日付）を取得"""
        try:
            # Redisからデータキャッシュを取得
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                latest = cached_data.get("latest")
                if latest and latest.get("date"):
                    return datetime.strptime(latest["date"], "%Y-%m-%d").date()

            # ファイルキャッシュからも試行
            file_cache = self._load_file_cache()
            if file_cache:
                latest = file_cache.get("latest")
                if latest and latest.get("date"):
                    return datetime.strptime(latest["date"], "%Y-%m-%d").date()

            return None
        except Exception as e:
            print(f"Error getting last release date: {e}")
            return None

    def _fetch_investing_schedule(self) -> Optional[Dict[str, Any]]:
        """
        Investing.comから次回発表日を取得

        ページ内の data-event-datetime 属性から次回発表日を抽出する。
        次回発表日が掲載されていない場合はNoneを返す（ブランク表示）。
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.investing.com/economic-calendar/",
            }

            response = requests.get(INVESTING_ECI_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            today = date.today()
            tomorrow = today + timedelta(days=1)

            # 方法1: data-event-datetime属性から次回発表日を探す
            for elem in soup.find_all(attrs={'data-event-datetime': True}):
                dt_str = elem.get('data-event-datetime', '')
                # 形式: "2025/01/31 22:30:00" など
                match = re.match(r'(\d{4})/(\d{2})/(\d{2})', dt_str)
                if match:
                    try:
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day_num = int(match.group(3))
                        release_date = date(year, month, day_num)
                        if release_date >= tomorrow:
                            print(f"Found ECI next release date from data-event-datetime: {release_date}")
                            return {
                                "date": release_date.strftime("%Y-%m-%d"),
                                "label": f"Employment Cost Index - {release_date.strftime('%Y/%m/%d')} 8:30 ET"
                            }
                    except ValueError:
                        continue

            # 次回発表日が見つからない場合はNone（ブランク表示）
            print("No ECI next release date found in Investing.com page")
            return None

        except Exception as e:
            print(f"Error fetching Investing.com ECI schedule: {e}")
            return None

    def _get_cached_schedule(self) -> Optional[Dict[str, Any]]:
        """キャッシュされた発表スケジュールを取得"""
        # Redisチェック
        cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached:
            cached_at = cached.get("cached_at")
            if cached_at:
                try:
                    cached_dt = datetime.fromisoformat(cached_at)
                    if cached_dt.tzinfo is None:
                        cached_dt = cached_dt.replace(tzinfo=JST)
                    # 30日間有効
                    if (datetime.now(JST) - cached_dt).days < 30:
                        return cached
                except Exception:
                    pass

        # ファイルキャッシュチェック
        try:
            if SCHEDULE_CACHE_FILE.exists():
                with open(SCHEDULE_CACHE_FILE, 'r', encoding='utf-8') as f:
                    file_cache = json.load(f)
                    cached_at = file_cache.get("cached_at")
                    if cached_at:
                        cached_dt = datetime.fromisoformat(cached_at)
                        if cached_dt.tzinfo is None:
                            cached_dt = cached_dt.replace(tzinfo=JST)
                        if (datetime.now(JST) - cached_dt).days < 30:
                            redis_client.set(self.SCHEDULE_CACHE_KEY, file_cache, expire=30*24*60*60)
                            return file_cache
        except Exception:
            pass

        return None

    def _save_schedule_cache(self, data: Dict[str, Any]) -> None:
        """発表スケジュールをキャッシュに保存"""
        try:
            data["cached_at"] = datetime.now(JST).isoformat()
            redis_client.set(self.SCHEDULE_CACHE_KEY, data, expire=30*24*60*60)

            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save ECI schedule cache: {e}")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load ECI file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"ECI cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save ECI file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Employment Cost Index",
            "source": "FRED / BLS",
            "series_id": ECIALLCIV_SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
employment_cost_index_service = EmploymentCostIndexService()
