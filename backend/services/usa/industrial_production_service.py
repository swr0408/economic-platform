"""
鉱工業生産（Industrial Production）サービス
FRED APIからINDPROデータを取得

シリーズID:
- INDPRO: Industrial Production: Total Index (Index 2017=100)

発表スケジュール:
- 毎月14〜18日頃の9:15 ET
- FRB G.17リリースページから次回発表日を自動取得

キャッシュ方式: last_updated判定（スケジュール時刻ベース）
スケジューラ: 発表日22:15 JST（9:15 ET + 14時間 = 23:15 JST、バッファ込みで22:15）
"""
import os
import json
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client
from services.usa.release_schedule_utils import INDUSTRIAL_PRODUCTION_CHECKER


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
INDPRO_SERIES_ID = "INDPRO"

# FRB G.17リリースページURL
FRB_G17_URL = "https://www.federalreserve.gov/releases/G17/default.htm"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "industrial_production_cache.json"


class IndustrialProductionService:
    """鉱工業生産（Industrial Production）サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:indpro"
    SCHEDULE_CACHE_KEY = "indpro:next_release"

    # 発表時刻設定
    RELEASE_TIME_ET = "09:15"  # 発表時刻(ET)
    RELEASE_TIME_JST_HOUR = 23  # 9:15 ET = 23:15 JST（冬時間）/ 22:15 JST（夏時間）

    # 月名のマッピング
    MONTH_MAP = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12
    }

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self.schedule_checker = INDUSTRIAL_PRODUCTION_CHECKER

    def get_industrial_production_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        鉱工業生産データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "mom": float, "yoy": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float, "mom": float, "yoy": float},
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
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
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
            # 変化率を計算
            processed_data = self._calculate_changes(api_data)
            latest = processed_data[-1] if processed_data else None

            cache_payload = {
                "data": processed_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（last_updated判定方式）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
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
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
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
        """FRED APIからデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching Industrial Production from FRED ({INDPRO_SERIES_ID})...")

            # デフォルト期間（2000年から）
            if not start_date:
                start_date = "2000-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": INDPRO_SERIES_ID,
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

            print(f"Fetched {len(result)} records from FRED (INDPRO)")
            return result

        except Exception as e:
            print(f"Error fetching Industrial Production: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """前月比・前年比を計算"""
        result = []

        for i, item in enumerate(data):
            entry = {
                "date": item["date"],
                "value": item["value"],
                "mom": None,  # Month-over-Month
                "yoy": None   # Year-over-Year
            }

            # 前月比（1ヶ月前のデータがあれば）
            if i >= 1:
                prev_value = data[i - 1]["value"]
                if prev_value and prev_value != 0:
                    entry["mom"] = round((item["value"] - prev_value) / prev_value * 100, 2)

            # 前年比（12ヶ月前のデータがあれば）
            if i >= 12:
                year_ago_value = data[i - 12]["value"]
                if year_ago_value and year_ago_value != 0:
                    entry["yoy"] = round((item["value"] - year_ago_value) / year_ago_value * 100, 2)

            result.append(entry)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return self.schedule_checker.should_refresh(last_updated_str)

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        """
        FRB G.17ページから次回発表日を取得

        Returns:
            {"date": "YYYY-MM-DD", "label": "January 16, 2025"} | None
        """
        # Redisキャッシュをチェック（24時間有効）
        cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached:
            cached_date = cached.get("date")
            if cached_date:
                # 次回発表日がまだ来ていなければキャッシュを使用
                try:
                    release_date = datetime.strptime(cached_date, "%Y-%m-%d").date()
                    if release_date >= date.today():
                        return cached
                except ValueError:
                    pass

        # FRB G.17ページからスクレイピング
        try:
            print(f"Fetching next release date from FRB G.17...")
            response = requests.get(FRB_G17_URL, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # ページ内のテキストから発表日を抽出
            # 「2025: January 16, February 18, ...」のようなパターンを探す
            text = soup.get_text()

            # 現在の年と来年の発表日を探す
            today = date.today()
            current_year = today.year
            next_year = current_year + 1

            next_release_date = None
            next_release_label = None

            for year in [current_year, next_year]:
                # 「2025: January 16, February 18, ...」のパターンを検索
                year_pattern = rf"{year}:\s*([A-Za-z]+\s+\d+(?:,\s*[A-Za-z]+\s+\d+)*)"
                match = re.search(year_pattern, text, re.IGNORECASE)

                if match:
                    dates_str = match.group(1)
                    # 「January 16」のようなパターンを抽出
                    date_pattern = r"([A-Za-z]+)\s+(\d+)"
                    date_matches = re.findall(date_pattern, dates_str)

                    for month_name, day in date_matches:
                        month_num = self.MONTH_MAP.get(month_name.lower())
                        if month_num:
                            try:
                                release_date = date(year, month_num, int(day))
                                # 今日以降の最初の発表日を見つける
                                if release_date >= today:
                                    next_release_date = release_date.strftime("%Y-%m-%d")
                                    next_release_label = f"{month_name} {day}, {year}"
                                    break
                            except ValueError:
                                continue

                    if next_release_date:
                        break

            if next_release_date:
                result = {
                    "date": next_release_date,
                    "label": next_release_label
                }
                # 24時間キャッシュ
                redis_client.set(self.SCHEDULE_CACHE_KEY, result, expire=86400)
                print(f"Next Industrial Production release: {next_release_label}")
                return result

        except Exception as e:
            print(f"Error fetching next release date: {e}")
            import traceback
            traceback.print_exc()

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

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "series_id": INDPRO_SERIES_ID,
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "schedule_status": self.schedule_checker.get_status(),
            "file_cache_exists": CACHE_FILE.exists()
        }


# シングルトンインスタンス
industrial_production_service = IndustrialProductionService()
