"""
Visa支出モメンタム指数サービス
FRED APIからVisa Spending Momentum Indexデータを取得

シリーズID:
- VISASMIHSA: Visa Spending Momentum Index (Seasonally Adjusted)

発表スケジュール:
- 毎月更新（具体的な発表日は不定）
- Visaサイトからスケジュールを取得（半年に1回程度更新）
- 発表日不明時: 1ヶ月経過後、新データがあるまで1日1回チェック

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import json
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

# FREDシリーズID
VISA_SMI_SERIES_ID = "VISASMIHSA"

# Visaリリーススケジュールページ
VISA_SMI_SCHEDULE_URL = "https://usa.visa.com/partner-with-us/visa-consulting-analytics/spending-momentum-index.html"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "visa_spending_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "visa_spending_schedule.json"


class VisaSpendingService:
    """Visa支出モメンタム指数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:series:visa_spending"
    SCHEDULE_CACHE_KEY = "visa:smi:schedule"
    ECONALPHA_ID = "visa_spending"  # FMPマッピング用ID

    # スケジュールキャッシュの有効期間（180日 = 約6ヶ月）
    SCHEDULE_CACHE_TTL = 180 * 24 * 60 * 60  # 15552000秒

    # データ更新チェック間隔（1日）
    DATA_CHECK_INTERVAL = 24 * 60 * 60  # 86400秒

    # 新データなし時の更新待機期間（30日 = 1ヶ月）
    NO_DATA_WAIT_PERIOD = 30  # 日数

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_visa_spending_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Visa支出モメンタム指数データを取得

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
                if last_updated_str and not self._should_refresh(last_updated_str, file_cache):
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
        """FRED APIからVisa支出モメンタム指数データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching Visa Spending Momentum Index from FRED...")

            # デフォルト期間（2015年から）
            if not start_date:
                start_date = "2015-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": VISA_SMI_SERIES_ID,
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

                # 前月比（1ヶ月前のデータがあれば）
                if i >= 1:
                    prev_value = raw_data[i - 1]["value"]
                    if prev_value and prev_value != 0:
                        entry["mom"] = round(item["value"] - prev_value, 2)

                # 前年比（12ヶ月前のデータがあれば）
                if i >= 12:
                    year_ago_value = raw_data[i - 12]["value"]
                    if year_ago_value and year_ago_value != 0:
                        entry["yoy"] = round(item["value"] - year_ago_value, 2)

                result.append(entry)

            print(f"Fetched {len(result)} records from FRED (Visa Spending)")
            return result

        except Exception as e:
            print(f"Error fetching Visa Spending: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        FMPスケジュールベースの3分方式で判定
        """
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)


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
            "series_id": VISA_SMI_SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
visa_spending_service = VisaSpendingService()
