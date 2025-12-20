"""
シカゴ連銀金融環境指数（NFCI）サービス
FRED APIからNFCIデータを取得

シリーズID:
- NFCI: Chicago Fed National Financial Conditions Index

発表スケジュール:
- 毎週水曜日 8:30 ET（祝日の場合は木曜日）
- 前週金曜日までのデータを発表

キャッシュ方式: last_updated判定（スケジュール時刻ベース）
スケジューラ: 水曜日22:00 JST（8:30 ET + 14時間 = 22:30 JST、バッファ込みで22:00）
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
NFCI_SERIES_ID = "NFCI"

# スケジュールファイルパス
SCHEDULE_FILE_PATH = Path(__file__).parent.parent.parent / "schedules" / "nfci_schedule.json"


class NFCIService:
    """シカゴ連銀金融環境指数（NFCI）サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:nfci"
    SCHEDULE_CACHE_KEY = "nfci:schedule"

    # スケジュール設定（年次更新用）
    DEFAULT_RELEASE_DAY = 2  # 水曜日（0=月曜, 2=水曜）
    RELEASE_TIME_ET = "08:30"  # 発表時刻(ET)

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_nfci_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        NFCIデータを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("latest"),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            # 最新値を取得
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（last_updated判定方式）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": api_data,
                "latest": latest,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "data": [],
            "latest": None,
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

            print(f"Fetching NFCI from FRED ({NFCI_SERIES_ID})...")

            # デフォルト期間（2000年から）
            if not start_date:
                start_date = "2000-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": NFCI_SERIES_ID,
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
                            "value": round(float(obs["value"]), 4)
                        })
                    except (ValueError, TypeError):
                        continue

            print(f"Fetched {len(result)} records from FRED (NFCI)")
            return result

        except Exception as e:
            print(f"Error fetching NFCI: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_next_release_date(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を取得

        スケジュールファイルがあればそれを使用、なければ動的に計算
        """
        # スケジュールファイルを確認
        schedule = self._load_schedule()
        if schedule:
            today = date.today()
            for entry in schedule:
                release_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
                if release_date > today:
                    return {
                        "date": entry["date"],
                        "time_et": entry.get("time_et", self.RELEASE_TIME_ET)
                    }

        # スケジュールファイルがない場合は動的に計算
        return self._calculate_next_release()

    def _calculate_next_release(self) -> Dict[str, Any]:
        """
        次回発表日を動的に計算

        NFCIは毎週水曜日8:30 ETに発表
        祝日の場合は木曜日にずれることがあるが、通常は水曜日と仮定
        """
        today = date.today()

        # 今週の水曜日を計算
        days_until_wednesday = (self.DEFAULT_RELEASE_DAY - today.weekday()) % 7
        if days_until_wednesday == 0:
            # 今日が水曜日の場合、発表時刻を過ぎているかチェック
            now_et = datetime.now(ET)
            release_time_today = now_et.replace(hour=8, minute=30, second=0, microsecond=0)
            if now_et > release_time_today:
                # 今日の発表時刻を過ぎているので来週
                days_until_wednesday = 7

        next_wednesday = today + timedelta(days=days_until_wednesday)

        return {
            "date": next_wednesday.strftime("%Y-%m-%d"),
            "time_et": self.RELEASE_TIME_ET
        }

    def _load_schedule(self) -> Optional[List[Dict[str, Any]]]:
        """スケジュールファイルを読み込む"""
        try:
            if SCHEDULE_FILE_PATH.exists():
                with open(SCHEDULE_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("releases", [])
        except Exception as e:
            print(f"Error loading NFCI schedule: {e}")
        return None

    def generate_schedule(self, year: int) -> List[Dict[str, Any]]:
        """
        年間スケジュールを生成

        Args:
            year: 対象年

        Returns:
            [{"date": "YYYY-MM-DD", "time_et": "08:30"}, ...]
        """
        schedule = []

        # 年始から年末までの全水曜日を列挙
        current = date(year, 1, 1)
        # 最初の水曜日を見つける
        while current.weekday() != self.DEFAULT_RELEASE_DAY:
            current += timedelta(days=1)

        # 年末まで水曜日を追加
        while current.year == year:
            schedule.append({
                "date": current.strftime("%Y-%m-%d"),
                "time_et": self.RELEASE_TIME_ET
            })
            current += timedelta(days=7)

        return schedule

    def save_schedule(self, year: int, schedule: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        スケジュールをファイルに保存

        Args:
            year: 対象年
            schedule: スケジュールリスト（Noneの場合は自動生成）

        Returns:
            保存成功かどうか
        """
        try:
            if schedule is None:
                schedule = self.generate_schedule(year)

            # ディレクトリを作成
            SCHEDULE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "series_id": NFCI_SERIES_ID,
                "year": year,
                "releases": schedule,
                "generated_at": datetime.now(JST).isoformat(),
                "note": "NFCI is released weekly on Wednesday at 8:30 ET. Holidays may shift to Thursday."
            }

            with open(SCHEDULE_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"Saved NFCI schedule for {year} ({len(schedule)} releases)")
            return True

        except Exception as e:
            print(f"Error saving NFCI schedule: {e}")
            return False

    def update_schedule_if_needed(self) -> bool:
        """
        スケジュールが古い場合（前年以前）に更新

        Returns:
            更新したかどうか
        """
        try:
            current_year = date.today().year

            # 既存のスケジュールをチェック
            if SCHEDULE_FILE_PATH.exists():
                with open(SCHEDULE_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    schedule_year = data.get("year", 0)

                    # 今年のスケジュールがあればOK
                    if schedule_year >= current_year:
                        return False

            # 今年と来年のスケジュールを生成
            schedule = []
            schedule.extend(self.generate_schedule(current_year))
            schedule.extend(self.generate_schedule(current_year + 1))

            return self.save_schedule(current_year, schedule)

        except Exception as e:
            print(f"Error updating NFCI schedule: {e}")
            return False

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "series_id": NFCI_SERIES_ID,
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self.get_next_release_date()
        }

    def get_latest_value(self) -> Optional[Dict[str, Any]]:
        """最新のNFCIを取得"""
        result = self.get_nfci_data()
        return result.get("latest")


# シングルトンインスタンス
nfci_service = NFCIService()
