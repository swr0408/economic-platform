"""
耐久財受注（Durable Goods Orders）サービス
FRED APIからDGORDER, ADXTNOデータを取得

シリーズID:
- DGORDER: Manufacturers' New Orders: Durable Goods (Millions of Dollars)
- ADXTNO: Manufacturers' New Orders: Durable Goods Excluding Transportation (Millions of Dollars)

発表スケジュール:
- Census.gov M3サーベイ Advance Report
- 毎月下旬 8:30 AM ET
- Census.govから次回発表日を自動取得

キャッシュ方式: last_updated判定（スケジュール時刻ベース）
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
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
DGORDER_SERIES_ID = "DGORDER"  # 耐久財新規受注
ADXTNO_SERIES_ID = "ADXTNO"   # 耐久財新規受注（輸送除外）

# Census.gov リリーススケジュールURL
CENSUS_M3_SCHEDULE_URL = "https://www.census.gov/manufacturing/m3/release_schedule.html"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "durable_goods_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "durable_goods_schedule.json"


class DurableGoodsService:
    """耐久財受注（Durable Goods Orders）サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:durable_goods"
    SCHEDULE_CACHE_KEY = "census:durable_goods:schedule"
    ECONALPHA_ID = "durable_goods_mom"  # FMPマッピング用ID

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_durable_goods_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        耐久財受注データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "ex_transport": float, "mom": float, "yoy": float, "ex_transport_mom": float, "ex_transport_yoy": float}, ...],
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
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": get_next_release_from_fmp('durable_goods_mom'),
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
                        "next_release": get_next_release_from_fmp('durable_goods_mom'),
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
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（last_updated判定方式）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp('durable_goods_mom'),
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
                "next_release": get_next_release_from_fmp('durable_goods_mom'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('durable_goods_mom'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(
        self,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """FRED APIから耐久財受注データを取得（両シリーズ）"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching Durable Goods Orders from FRED...")

            # デフォルト期間（2000年から）
            if not start_date:
                start_date = "2000-01-01"

            # DGORDERとADXTNOを両方取得
            dgorder_data = self._fetch_series(DGORDER_SERIES_ID, start_date)
            adxtno_data = self._fetch_series(ADXTNO_SERIES_ID, start_date)

            if not dgorder_data:
                return []

            # ADXTNOを日付ベースの辞書に変換
            adxtno_dict = {item["date"]: item["value"] for item in adxtno_data}

            # データをマージして変化率を計算
            result = []
            for i, item in enumerate(dgorder_data):
                entry = {
                    "date": item["date"],
                    "value": item["value"],
                    "ex_transport": adxtno_dict.get(item["date"]),
                    "mom": None,
                    "yoy": None,
                    "ex_transport_mom": None,
                    "ex_transport_yoy": None
                }

                # 前月比（1ヶ月前のデータがあれば）
                if i >= 1:
                    prev_value = dgorder_data[i - 1]["value"]
                    if prev_value and prev_value != 0:
                        entry["mom"] = round((item["value"] - prev_value) / prev_value * 100, 2)

                    # 輸送除外の前月比
                    prev_ex = adxtno_dict.get(dgorder_data[i - 1]["date"])
                    curr_ex = entry["ex_transport"]
                    if prev_ex and prev_ex != 0 and curr_ex:
                        entry["ex_transport_mom"] = round((curr_ex - prev_ex) / prev_ex * 100, 2)

                # 前年比（12ヶ月前のデータがあれば）
                if i >= 12:
                    year_ago_value = dgorder_data[i - 12]["value"]
                    if year_ago_value and year_ago_value != 0:
                        entry["yoy"] = round((item["value"] - year_ago_value) / year_ago_value * 100, 2)

                    # 輸送除外の前年比
                    year_ago_ex = adxtno_dict.get(dgorder_data[i - 12]["date"])
                    curr_ex = entry["ex_transport"]
                    if year_ago_ex and year_ago_ex != 0 and curr_ex:
                        entry["ex_transport_yoy"] = round((curr_ex - year_ago_ex) / year_ago_ex * 100, 2)

                result.append(entry)

            print(f"Fetched {len(result)} records from FRED (Durable Goods)")
            return result

        except Exception as e:
            print(f"Error fetching Durable Goods: {e}")
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
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)


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
            "series_ids": [DGORDER_SERIES_ID, ADXTNO_SERIES_ID],
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": CACHE_FILE.exists()
        }


# シングルトンインスタンス
durable_goods_service = DurableGoodsService()
