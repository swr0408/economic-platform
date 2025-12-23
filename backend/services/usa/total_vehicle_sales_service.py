"""
自動車販売台数サービス
FRED APIからTotal Vehicle Sales（TOTALSA）データを取得

シリーズID:
- TOTALSA: Total Vehicle Sales (Seasonally Adjusted Annual Rate, Millions of Units)

発表スケジュール:
- BEA (Bureau of Economic Analysis) により毎月発表
- FRED Release ID: 93 (Supplemental Estimates, Motor Vehicles)
- 発表日はFRED releases/datesエンドポイントから自動取得

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
TOTALSA_SERIES_ID = "TOTALSA"

# FREDリリースID（Supplemental Estimates, Motor Vehicles）
FRED_RELEASE_ID = 93

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "total_vehicle_sales_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "total_vehicle_sales_schedule.json"


class TotalVehicleSalesService:
    """自動車販売台数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:series:total_vehicle_sales"
    SCHEDULE_CACHE_KEY = "fred:release:93:schedule"

    # スケジュールキャッシュの有効期間（180日 = 約6ヶ月）
    SCHEDULE_CACHE_TTL = 180 * 24 * 60 * 60  # 15552000秒

    # データ更新チェック間隔（1日）
    DATA_CHECK_INTERVAL = 24 * 60 * 60  # 86400秒

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_total_vehicle_sales_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        自動車販売台数データを取得

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
        """FRED APIから自動車販売台数データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching Total Vehicle Sales from FRED...")

            # デフォルト期間（1990年から）
            if not start_date:
                start_date = "1990-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": TOTALSA_SERIES_ID,
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

                # 前月比（1ヶ月前のデータがあれば、%表示）
                if i >= 1:
                    prev_value = raw_data[i - 1]["value"]
                    if prev_value and prev_value != 0:
                        mom_pct = ((item["value"] - prev_value) / prev_value) * 100
                        entry["mom"] = round(mom_pct, 2)

                # 前年比（12ヶ月前のデータがあれば、%表示）
                if i >= 12:
                    year_ago_value = raw_data[i - 12]["value"]
                    if year_ago_value and year_ago_value != 0:
                        yoy_pct = ((item["value"] - year_ago_value) / year_ago_value) * 100
                        entry["yoy"] = round(yoy_pct, 2)

                result.append(entry)

            print(f"Fetched {len(result)} records from FRED (Total Vehicle Sales)")
            return result

        except Exception as e:
            print(f"Error fetching Total Vehicle Sales: {e}")
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
                if days_since_update >= 30:
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

        FRED releases/datesエンドポイントからスケジュールを取得
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
                        # 今日以降の発表日を検索
                        releases = cached.get("releases", [])
                        next_rel = self._find_next_release_from_list(releases)
                        if next_rel:
                            return next_rel
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
                        releases = schedule_cache.get("releases", [])
                        next_rel = self._find_next_release_from_list(releases)
                        if next_rel:
                            # Redisにも保存
                            redis_client.set(self.SCHEDULE_CACHE_KEY, schedule_cache, expire=self.SCHEDULE_CACHE_TTL)
                            return next_rel
                except Exception:
                    pass

        # FRED APIから取得
        releases = self._fetch_release_schedule()
        if releases:
            # キャッシュに保存（6ヶ月間有効）
            cache_data = {
                "releases": releases,
                "cached_at": datetime.now(JST).isoformat()
            }
            redis_client.set(self.SCHEDULE_CACHE_KEY, cache_data, expire=self.SCHEDULE_CACHE_TTL)
            self._save_file_cache(SCHEDULE_CACHE_FILE, cache_data)
            return self._find_next_release_from_list(releases)

        return None

    def _fetch_release_schedule(self) -> List[Dict[str, Any]]:
        """
        FRED APIからリリーススケジュールを取得

        releases/datesエンドポイントを使用
        """
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching release schedule from FRED (Release ID: {FRED_RELEASE_ID})...")

            # 今日から1年後までのスケジュールを取得
            today = date.today()
            end_date = today + timedelta(days=365)

            url = f"{self.BASE_URL}/release/dates"
            params = {
                "release_id": FRED_RELEASE_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "realtime_start": today.strftime("%Y-%m-%d"),
                "realtime_end": end_date.strftime("%Y-%m-%d"),
                "include_release_dates_with_no_data": "true"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            releases = []
            for item in data.get("release_dates", []):
                release_date = item.get("date")
                if release_date:
                    releases.append({
                        "date": release_date,
                        "label": f"Total Vehicle Sales - {release_date}"
                    })

            print(f"Fetched {len(releases)} upcoming release dates")
            return releases

        except Exception as e:
            print(f"Error fetching release schedule: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _find_next_release_from_list(self, releases: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """リリースリストから次回発表日を検索"""
        today = date.today()

        for rel in releases:
            release_date_str = rel.get("date")
            if release_date_str:
                try:
                    release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                    if release_date >= today:
                        return {
                            "date": release_date_str,
                            "label": rel.get("label", f"Total Vehicle Sales - {release_date_str}")
                        }
                except ValueError:
                    continue

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
            "series_id": TOTALSA_SERIES_ID,
            "release_id": FRED_RELEASE_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
total_vehicle_sales_service = TotalVehicleSalesService()
