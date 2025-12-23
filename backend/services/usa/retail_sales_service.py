"""
小売売上高（Advance Monthly Retail Trade Report）サービス
FRED APIから小売売上高データを取得

シリーズID:
- RSAFS: Advance Retail Sales: Retail and Food Services（総合）
- RSFSXMV: Advance Retail Sales: Retail (Excluding Motor Vehicle and Parts)（自動車除く）

コントロールグループは別サービス（retail_control_service）で取得

発表スケジュール:
- Census.gov Advance Monthly Retail Trade Report
- 毎月中旬 8:30 AM ET
- Census.govから次回発表日を自動取得

キャッシュ方式: last_updated判定（スケジュール時刻ベース）
"""
import os
import json
from datetime import datetime, date
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
RSAFS_SERIES_ID = "RSAFS"  # 小売売上高（全体、SA、百万ドル）
RSFSXMV_SERIES_ID = "RSFSXMV"  # 小売売上高（自動車除く）

# Census.gov リリーススケジュールURL
CENSUS_RETAIL_SCHEDULE_URL = "https://www.census.gov/retail/release_schedule.html"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "retail_sales_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "retail_sales_schedule.json"


class RetailSalesService:
    """小売売上高（Advance Monthly Retail Trade Report）サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:retail_sales"
    SCHEDULE_CACHE_KEY = "census:retail_sales:schedule"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_retail_sales_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        小売売上高データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "ex_auto": float, "mom": float, "yoy": float, ...}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
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
                    data = file_cache.get("data", [])
                    next_release = self._get_next_release()

                    # Redisにも保存
                    redis_client.set(self.CACHE_KEY, {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "last_updated": last_updated_str
                    }, expire=0)

                    return {
                        "data": data,
                        "latest": data[-1] if data else None,
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None
            next_release = self._get_next_release()

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（last_updated判定方式）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
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
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
                "next_release": self._get_next_release(),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": self._get_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(
        self,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """FRED APIから小売売上高データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching Retail Sales from FRED...")

            # デフォルト期間（2000年から）
            if not start_date:
                start_date = "2000-01-01"

            # シリーズを取得
            rsafs_data = self._fetch_series(RSAFS_SERIES_ID, start_date)
            rsfsxmv_data = self._fetch_series(RSFSXMV_SERIES_ID, start_date)

            if not rsafs_data:
                return []

            # 日付ベースの辞書に変換
            rsfsxmv_dict = {item["date"]: item["value"] for item in rsfsxmv_data}

            # データをマージして変化率を計算
            result = []
            for i, item in enumerate(rsafs_data):
                entry = {
                    "date": item["date"],
                    "value": item["value"],  # 小売売上高（百万ドル）
                    "ex_auto": rsfsxmv_dict.get(item["date"]),  # 自動車除く
                    "mom": None,
                    "yoy": None,
                    "ex_auto_mom": None,
                    "ex_auto_yoy": None
                }

                # 前月比（1ヶ月前のデータがあれば）
                if i >= 1:
                    prev_value = rsafs_data[i - 1]["value"]
                    if prev_value and prev_value != 0:
                        entry["mom"] = round((item["value"] - prev_value) / prev_value * 100, 2)

                    # 自動車除くの前月比
                    prev_ex = rsfsxmv_dict.get(rsafs_data[i - 1]["date"])
                    curr_ex = entry["ex_auto"]
                    if prev_ex and prev_ex != 0 and curr_ex:
                        entry["ex_auto_mom"] = round((curr_ex - prev_ex) / prev_ex * 100, 2)

                # 前年比（12ヶ月前のデータがあれば）
                if i >= 12:
                    year_ago_value = rsafs_data[i - 12]["value"]
                    if year_ago_value and year_ago_value != 0:
                        entry["yoy"] = round((item["value"] - year_ago_value) / year_ago_value * 100, 2)

                    # 自動車除くの前年比
                    year_ago_ex = rsfsxmv_dict.get(rsafs_data[i - 12]["date"])
                    curr_ex = entry["ex_auto"]
                    if year_ago_ex and year_ago_ex != 0 and curr_ex:
                        entry["ex_auto_yoy"] = round((curr_ex - year_ago_ex) / year_ago_ex * 100, 2)

                result.append(entry)

            print(f"Fetched {len(result)} records from FRED (Retail Sales)")
            return result

        except Exception as e:
            print(f"Error fetching Retail Sales: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_series(self, series_id: str, start_date: str) -> List[Dict[str, Any]]:
        """FREDから単一シリーズを取得"""
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

            result = []
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        result.append({
                            "date": obs["date"],
                            "value": round(float(obs["value"]), 2)
                        })
                    except (ValueError, TypeError):
                        continue

            return result

        except Exception as e:
            print(f"Error fetching series {series_id}: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - 次回発表日時を過ぎており、かつ最終更新がそれより前なら更新が必要
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 次回発表情報を取得
            next_release = self._get_next_release()
            if not next_release:
                # 発表情報がない場合は月1回程度の更新を想定
                days_since_update = (now - last_updated).days
                return days_since_update >= 30

            # 発表日時をパース
            release_date_str = next_release.get("date")
            if not release_date_str:
                return False

            release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

            # 夏時間判定
            is_dst = self._is_dst(now)
            release_hour = 21 if is_dst else 22  # 8:30 ET → 21:30/22:30 JST

            release_datetime = datetime(
                release_date.year, release_date.month, release_date.day,
                release_hour, 30, 0, tzinfo=JST
            )

            # 発表日時を過ぎており、かつ最終更新が発表日時より前なら更新が必要
            if now >= release_datetime and last_updated < release_datetime:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _is_dst(self, dt: datetime) -> bool:
        """米国東部時間が夏時間かどうかを判定"""
        try:
            et_time = dt.astimezone(ET)
            return bool(et_time.dst())
        except Exception:
            # 3月第2日曜〜11月第1日曜を夏時間と仮定
            if dt.month > 3 and dt.month < 11:
                return True
            if dt.month == 3:
                second_sunday = 14 - (date(dt.year, 3, 1).weekday() + 1) % 7
                return dt.day >= second_sunday
            if dt.month == 11:
                first_sunday = 7 - (date(dt.year, 11, 1).weekday() + 1) % 7
                return dt.day < first_sunday
            return False

    # スケジュールキャッシュの有効期間（30日 = 1ヶ月）
    SCHEDULE_CACHE_TTL = 30 * 24 * 60 * 60  # 2592000秒

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得

        Census.govからスクレイピングして取得
        キャッシュがあればそれを使用（1ヶ月間有効）
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
                    # キャッシュは1ヶ月間有効
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
        schedule_cache = self._load_schedule_cache()
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

        # Census.govページからスクレイピング
        scraped = self._scrape_next_release()
        if scraped:
            # キャッシュに保存（1ヶ月間有効）
            cache_data = {
                **scraped,
                "cached_at": datetime.now(JST).isoformat()
            }
            redis_client.set(self.SCHEDULE_CACHE_KEY, cache_data, expire=self.SCHEDULE_CACHE_TTL)
            self._save_schedule_cache(cache_data)
            return scraped

        return None

    def _scrape_next_release(self) -> Optional[Dict[str, Any]]:
        """
        Census.gov Retail Sales リリーススケジュールから次回発表日をスクレイピング

        ページ構造:
        - Advance Monthly Retail Trade Reportのテーブルを探す
        - Reference Month列とRelease Dates列を解析
        """
        try:
            print("Scraping next Retail Sales release date from Census.gov...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(CENSUS_RETAIL_SCHEDULE_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # テーブルを探す
            tables = soup.find_all("table")
            today = date.today()

            for table in tables:
                # テーブルの中身を確認
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        # 日付を探す
                        for cell in cells[1:]:  # 最初の列はReference Month
                            date_text = cell.get_text(strip=True)
                            parsed_date = self._parse_date_string(date_text)
                            if parsed_date and parsed_date >= today:
                                # Reference monthは1列目
                                reference_month = cells[0].get_text(strip=True)
                                return {
                                    "date": parsed_date.strftime("%Y-%m-%d"),
                                    "label": f"Retail Sales ({reference_month}) - {parsed_date.strftime('%b %d, %Y')}"
                                }

            print("Could not find next release date on Census.gov page")
            return None

        except Exception as e:
            print(f"Error scraping Census.gov page: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_date_string(self, date_str: str) -> Optional[date]:
        """日付文字列をパース"""
        # 文字列のクリーンアップ
        date_str = date_str.strip()
        if not date_str or date_str.lower() in ["to be announced", "tba", "-"]:
            return None

        try:
            # "Month DD, YYYY" 形式 (例: "February 14, 2025")
            formats = [
                "%B %d, %Y",     # February 14, 2025
                "%b %d, %Y",     # Feb 14, 2025
                "%B %d %Y",      # February 14 2025
                "%b %d %Y",      # Feb 14 2025
                "%m/%d/%Y",      # 02/14/2025
                "%Y-%m-%d",      # 2025-02-14
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue

            # "(8:30 am)" などの時刻部分を除去して再試行
            import re
            date_str_clean = re.sub(r'\s*\([^)]*\)', '', date_str)
            for fmt in formats:
                try:
                    return datetime.strptime(date_str_clean.strip(), fmt).date()
                except ValueError:
                    continue

        except Exception:
            pass

        return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not CACHE_FILE.exists():
                return None

            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {CACHE_FILE}")
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
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Schedule cache saved to {SCHEDULE_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save schedule cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "series_ids": [RSAFS_SERIES_ID, RSFSXMV_SERIES_ID],
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": CACHE_FILE.exists()
        }


# シングルトンインスタンス
retail_sales_service = RetailSalesService()
