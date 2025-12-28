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
from services.usa.release_schedule_utils import VEHICLE_SALES_CHECKER


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
        self.schedule_checker = VEHICLE_SALES_CHECKER

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
                "next_release": None,
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
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache(DATA_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])

                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    return {
                        "data": data,
                        "latest": file_cache.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date)

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
                "next_release": None,
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
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
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

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定
        """
        return self.schedule_checker.should_refresh(last_updated_str)

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
            "schedule_status": self.schedule_checker.get_status(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
total_vehicle_sales_service = TotalVehicleSalesService()
