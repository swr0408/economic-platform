"""
JOLTS求人 / Indeed求人件数サービス
FRED APIからデータを取得

指標:
- JTSJOL: JOLTS Job Openings（JOLTS求人件数、千人）
- IHLIDXUS: Indeed Job Postings Index（Indeed求人件数指数）

データソース:
- FRED: https://fred.stlouisfed.org/series/JTSJOL
- FRED: https://fred.stlouisfed.org/series/IHLIDXUS
- Investing.com: https://jp.investing.com/economic-calendar/jolts-job-openings-1057

発表スケジュール:
- JOLTS: 毎月上旬（参照月の翌々月初旬）
- Indeed: 日次更新
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
JOLTS_SERIES_ID = "JTSJOL"       # JOLTS求人件数（千人）
INDEED_SERIES_ID = "IHLIDXUS"   # Indeed求人件数指数

# Investing.com JOLTS経済カレンダーURL
INVESTING_JOLTS_URL = "https://jp.investing.com/economic-calendar/jolts-job-openings-1057"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "jolts_indeed_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "jolts_schedule.json"

# 月名マッピング
MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9,
    'oct': 10, 'nov': 11, 'dec': 12
}

# 系列設定
SERIES_CONFIG = {
    "jolts": {
        "series_id": JOLTS_SERIES_ID,
        "name": "JOLTS求人件数",
        "name_en": "JOLTS Job Openings",
        "color": "#1890ff"  # 青
    },
    "indeed": {
        "series_id": INDEED_SERIES_ID,
        "name": "Indeed求人件数指数",
        "name_en": "Indeed Job Postings Index",
        "color": "#ff4d4f"  # 赤
    }
}


class JoltsIndeedService:
    """JOLTS求人 / Indeed求人件数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:jolts_indeed:data"
    SCHEDULE_CACHE_KEY = "fred:jolts:schedule"

    # 発表時刻設定（ET）- 10:00 AM ET
    RELEASE_HOUR_ET = 10
    RELEASE_MINUTE_ET = 0

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_jolts_indeed_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        JOLTS / Indeed求人データを取得

        Returns:
            {
                "data": [{"date": str, "jolts": float, "indeed": float}, ...],
                "latest": {...},
                "series_config": {...},
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
                        "series_config": SERIES_CONFIG,
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
                        "series_config": SERIES_CONFIG,
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)
        next_release = self._get_next_release()

        if api_data:
            latest = self._get_latest_values(api_data)

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
                "series_config": SERIES_CONFIG,
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
                "series_config": SERIES_CONFIG,
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "series_config": SERIES_CONFIG,
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _get_latest_values(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """JOLTSとIndeedそれぞれの最新値を取得"""
        latest = {
            "date": None,
            "jolts": None,
            "jolts_date": None,
            "indeed": None,
            "indeed_date": None
        }

        # 逆順で最新値を探す
        for item in reversed(data):
            if latest["jolts"] is None and item.get("jolts") is not None:
                latest["jolts"] = item["jolts"]
                latest["jolts_date"] = item["date"]
            if latest["indeed"] is None and item.get("indeed") is not None:
                latest["indeed"] = item["indeed"]
                latest["indeed_date"] = item["date"]
            if latest["jolts"] is not None and latest["indeed"] is not None:
                break

        # 全体の日付は最新のものを使用
        if data:
            latest["date"] = data[-1]["date"]

        return latest

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIからデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching JOLTS / Indeed data from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # JOLTS求人件数
            jolts_raw = self._fetch_series(JOLTS_SERIES_ID, start_date)
            # Indeed求人件数指数
            indeed_raw = self._fetch_series(INDEED_SERIES_ID, start_date)

            if not jolts_raw and not indeed_raw:
                return None

            # データをマージ
            merged_data = self._merge_data(jolts_raw, indeed_raw)

            print(f"Fetched {len(merged_data)} JOLTS / Indeed records")
            return merged_data

        except Exception as e:
            print(f"Error fetching JOLTS / Indeed data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_series(self, series_id: str, start_date: str) -> List[Dict[str, Any]]:
        """FRED APIからシリーズデータを取得"""
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc"
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
                        "value": round(value, 1)
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching FRED series {series_id}: {e}")
            return []

    def _merge_data(
        self,
        jolts_data: List[Dict[str, Any]],
        indeed_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """JOLTSとIndeedのデータをマージ"""
        # 日付でインデックス化
        jolts_map = {item["date"]: item["value"] for item in jolts_data}
        indeed_map = {item["date"]: item["value"] for item in indeed_data}

        # 全日付を収集
        all_dates = sorted(set(list(jolts_map.keys()) + list(indeed_map.keys())))

        result = []
        for d in all_dates:
            entry = {
                "date": d,
                "jolts": jolts_map.get(d),
                "indeed": indeed_map.get(d)
            }
            # 少なくとも1つの値がある場合のみ追加
            if entry["jolts"] is not None or entry["indeed"] is not None:
                result.append(entry)

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
        """次回発表日を取得（Investing.comからスクレイピング）"""
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
                # ただし、1日以内にスクレイピングしていたら再取得しない（過剰アクセス防止）
                cached_at = cached_schedule.get("cached_at")
                if cached_at:
                    try:
                        cached_dt = datetime.fromisoformat(cached_at)
                        if cached_dt.tzinfo is None:
                            cached_dt = cached_dt.replace(tzinfo=JST)
                        hours_since_cache = (datetime.now(JST) - cached_dt).total_seconds() / 3600
                        if hours_since_cache < 48:
                            # 48時間以内にスクレイピング済み → キャッシュの値を返す（None含む）
                            return None
                    except Exception:
                        pass

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

            response = requests.get(INVESTING_JOLTS_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            today = date.today()
            tomorrow = today + timedelta(days=1)

            # 方法1: data-event-datetime属性から次回発表日を探す
            for elem in soup.find_all(attrs={'data-event-datetime': True}):
                dt_str = elem.get('data-event-datetime', '')
                # 形式: "2025/01/10 22:30:00" など
                match = re.match(r'(\d{4})/(\d{2})/(\d{2})', dt_str)
                if match:
                    try:
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day_num = int(match.group(3))
                        release_date = date(year, month, day_num)
                        if release_date >= tomorrow:
                            print(f"Found JOLTS next release date from data-event-datetime: {release_date}")
                            return {
                                "date": release_date.strftime("%Y-%m-%d"),
                                "label": f"JOLTS Job Openings - {release_date.strftime('%Y/%m/%d')} 10:00 ET"
                            }
                    except ValueError:
                        continue

            # 次回発表日が見つからない場合はNone（ブランク表示）
            print("No JOLTS next release date found in Investing.com page")
            return None

        except Exception as e:
            print(f"Error fetching Investing.com JOLTS schedule: {e}")
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
            print(f"Failed to save JOLTS schedule cache: {e}")

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
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "JOLTS / Indeed Job Postings",
            "source": "FRED / BLS",
            "series_ids": [JOLTS_SERIES_ID, INDEED_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
jolts_indeed_service = JoltsIndeedService()
