"""
単位労働コスト / 労働生産性サービス
FRED APIからデータを取得

指標:
- PRS85006112: Nonfarm Business Sector: Unit Labor Costs (前期比)
- PRS85006092: Nonfarm Business Sector: Labor Productivity (前期比)

データソース:
- FRED: https://fred.stlouisfed.org/series/PRS85006112
- FRED: https://fred.stlouisfed.org/series/PRS85006092
- Investing.com: https://jp.investing.com/economic-calendar/unit-labor-costs-303

発表スケジュール:
- BLS Productivity and Costs
- 四半期ごと発表（2月、3月、5月、6月、8月、9月、11月、12月）
- 8:30 AM ET
- 3月、6月、9月、12月以外の月の15日以降に次回発表日を確認

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
UNIT_LABOR_COSTS_SERIES_ID = "PRS85006112"  # Unit Labor Costs
LABOR_PRODUCTIVITY_SERIES_ID = "PRS85006092"  # Labor Productivity

# Investing.com 単位労働コスト 経済カレンダーURL
INVESTING_ULC_URL = "https://jp.investing.com/economic-calendar/unit-labor-costs-303"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "unit_labor_cost_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "ulc_schedule.json"


class UnitLaborCostService:
    """単位労働コスト / 労働生産性サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:unit_labor_cost:data"
    SCHEDULE_CACHE_KEY = "bls:ulc:schedule"

    # 発表時刻設定（ET）- 8:30 AM ET
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_unit_labor_cost_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        単位労働コスト / 労働生産性データを取得（前期比）

        Returns:
            {
                "data": [{"date": str, "ulc_pch": float, "productivity_pch": float}, ...],
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
        """FRED APIから単位労働コスト・労働生産性データを取得（前期比 = pch）"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Unit Labor Cost / Labor Productivity (pch) from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 単位労働コスト（前期比）
            ulc_data = self._fetch_series(UNIT_LABOR_COSTS_SERIES_ID, start_date)

            # 労働生産性（前期比）
            productivity_data = self._fetch_series(LABOR_PRODUCTIVITY_SERIES_ID, start_date)

            if not ulc_data and not productivity_data:
                return None

            # データをマージ
            result = self._merge_data(ulc_data or [], productivity_data or [])

            print(f"Fetched {len(result)} Unit Labor Cost / Labor Productivity records")
            return result

        except Exception as e:
            print(f"Error fetching Unit Labor Cost data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_series(self, series_id: str, start_date: str) -> Optional[List[Dict[str, Any]]]:
        """FREDから単一シリーズのデータを取得（既に前期比）"""
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc",
                # 注: PRS85006112/PRS85006092は既に前期比(%)なのでunitsパラメータ不要
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
                    value = float(value_str)
                    result.append({
                        "date": obs["date"],
                        "value": round(value, 2)
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching series {series_id}: {e}")
            return None

    def _merge_data(
        self,
        ulc_data: List[Dict[str, Any]],
        productivity_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """単位労働コストと労働生産性データをマージ"""
        date_map: Dict[str, Dict[str, Any]] = {}

        for item in ulc_data:
            date_str = item["date"]
            date_map[date_str] = {
                "date": date_str,
                "ulc_pch": item["value"],
                "productivity_pch": None
            }

        for item in productivity_data:
            date_str = item["date"]
            if date_str in date_map:
                date_map[date_str]["productivity_pch"] = item["value"]
            else:
                date_map[date_str] = {
                    "date": date_str,
                    "ulc_pch": None,
                    "productivity_pch": item["value"]
                }

        # 日付順にソート
        result = sorted(date_map.values(), key=lambda x: x["date"])
        return result

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
        - 3月、6月、9月、12月以外の月の15日以降
        - 72時間おきにチェック
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
        1. 3月、6月、9月、12月の場合はスクレイピングしない（四半期末は発表なし）
        2. それ以外の月の15日以降に72時間おきにチェック
        """
        try:
            now = datetime.now(JST)
            current_month = now.month
            current_day = now.day

            # 四半期末月（3月、6月、9月、12月）はスクレイピングしない
            if current_month in [3, 6, 9, 12]:
                print(f"ULC: Skipping scrape in quarter-end month ({current_month})")
                return False

            # 15日未満はスクレイピングしない
            if current_day < 15:
                print(f"ULC: Day {current_day} < 15, waiting until 15th")
                return False

            # 前回スクレイピングから72時間経過しているかチェック
            cached_at = cached_schedule.get("cached_at")
            if cached_at:
                try:
                    cached_dt = datetime.fromisoformat(cached_at)
                    if cached_dt.tzinfo is None:
                        cached_dt = cached_dt.replace(tzinfo=JST)
                    hours_since_cache = (now - cached_dt).total_seconds() / 3600

                    # 72時間（3日）以内にスクレイピング済みならスキップ
                    if hours_since_cache < 72:
                        print(f"ULC: Last scraped {hours_since_cache:.1f} hours ago, waiting until 72 hours")
                        return False
                except Exception:
                    pass

            # スクレイピング実行
            print(f"ULC: Ready to scrape schedule (month {current_month}, day {current_day}, >72 hours since last scrape)")
            return True

        except Exception as e:
            print(f"Error checking scrape timing: {e}")
            return True  # エラー時はスクレイピングを試行

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
                "Referer": "https://jp.investing.com/economic-calendar/",
            }

            response = requests.get(INVESTING_ULC_URL, headers=headers, timeout=30)
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
                            print(f"Found ULC next release date from data-event-datetime: {release_date}")
                            return {
                                "date": release_date.strftime("%Y-%m-%d"),
                                "label": f"Unit Labor Costs - {release_date.strftime('%Y/%m/%d')} 8:30 ET"
                            }
                    except ValueError:
                        continue

            # 次回発表日が見つからない場合はNone（ブランク表示）
            print("No ULC next release date found in Investing.com page")
            return None

        except Exception as e:
            print(f"Error fetching Investing.com ULC schedule: {e}")
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
            print(f"Failed to save ULC schedule cache: {e}")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load ULC file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"ULC cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save ULC file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Unit Labor Cost / Labor Productivity",
            "source": "FRED / BLS",
            "series_ids": [UNIT_LABOR_COSTS_SERIES_ID, LABOR_PRODUCTIVITY_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
unit_labor_cost_service = UnitLaborCostService()
