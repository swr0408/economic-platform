"""
設備稼働率（Capacity Utilization）サービス
FRED APIからTCUデータを取得

シリーズID:
- TCU: Capacity Utilization: Total Industry (Percent)

発表スケジュール:
- 毎月14〜18日頃の9:15 ET（Industrial Productionと同時発表）
- FRB G.17リリースページから次回発表日を自動取得

キャッシュ方式: last_updated判定（スケジュール時刻ベース）
スケジューラ: 発表日22:15 JST（9:15 ET + 14時間 = 23:15 JST、バッファ込みで22:15）
"""
import os
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
TCU_SERIES_ID = "TCU"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "capacity_utilization_cache.json"


class CapacityUtilizationService:
    """設備稼働率（Capacity Utilization）サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:tcu"
    SCHEDULE_CACHE_KEY = "indpro:next_release"  # Industrial Productionと同じ発表日

    # 発表時刻設定
    RELEASE_TIME_ET = "09:15"  # 発表時刻(ET)
    RELEASE_TIME_JST_HOUR = 23  # 9:15 ET = 23:15 JST（冬時間）/ 22:15 JST（夏時間）

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_capacity_utilization_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        設備稼働率データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float},
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
        """FRED APIからデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching Capacity Utilization from FRED ({TCU_SERIES_ID})...")

            # デフォルト期間（2000年から）
            if not start_date:
                start_date = "2000-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": TCU_SERIES_ID,
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

            print(f"Fetched {len(result)} records from FRED (TCU)")
            return result

        except Exception as e:
            print(f"Error fetching Capacity Utilization: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        Capacity Utilization発表スケジュール:
        - 発表日: 毎月14〜18日頃の9:15 ET（Industrial Productionと同時）
        - Industrial Productionの次回発表日キャッシュを参照

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
                # 最終更新から30日以上経過していれば更新
                days_since_update = (now - last_updated).days
                return days_since_update >= 30

            # 発表日時をパース
            release_date_str = next_release.get("date")
            if not release_date_str:
                return False

            release_date = datetime.strptime(release_date_str, "%Y-%m-%d")

            # 夏時間判定
            is_dst = self._is_dst(now)
            release_hour = 22 if is_dst else 23  # 9:15 ET → 22:15/23:15 JST

            release_datetime = datetime(
                release_date.year, release_date.month, release_date.day,
                release_hour, 15, 0, tzinfo=JST
            )

            # 発表日時を過ぎており、かつ最終更新が発表日時より前なら更新が必要
            if now >= release_datetime and last_updated < release_datetime:
                return True

            # 過去の発表日もチェック（見逃し対策）
            if release_datetime < now and last_updated < release_datetime:
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

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得

        Industrial Productionと同じ発表日なので、
        INDPROの次回発表日キャッシュを参照
        """
        # Industrial Productionの次回発表日キャッシュを参照
        cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached:
            release_date_str = cached.get("date")
            if release_date_str:
                try:
                    release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
                    if release_date >= date.today():
                        return {
                            "date": cached.get("date"),
                            "label": f"Capacity Utilization ({release_date.strftime('%b %d, %Y')})"
                        }
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

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "series_id": TCU_SERIES_ID,
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": CACHE_FILE.exists()
        }


# シングルトンインスタンス
capacity_utilization_service = CapacityUtilizationService()
