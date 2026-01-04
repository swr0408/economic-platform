"""
クレジットカードローン延滞率サービス
FRED APIからDelinquency Rate on Consumer Loansデータを取得

シリーズID:
- DRCCLACBS: Delinquency Rate on Consumer Loans, All Commercial Banks
  (四半期、季節調整済み、パーセント)

データソース:
- FRB Charge-Off and Delinquency Rates on Loans and Leases at Commercial Banks
- https://www.federalreserve.gov/releases/chargeoff/

発表スケジュール:
- 四半期末60日後に発表（2月・5月・8月・11月）
- 2月・5月・8月・11月の15日過ぎに1日1回チェック
- 発表時刻: 約10:00 ET

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
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FREDシリーズID
SERIES_ID = "DRCCLACBS"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "delinquency_rate_cache.json"


class DelinquencyRateService:
    """クレジットカードローン延滞率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:series:delinquency_rate"
    ECONALPHA_ID = "delinquency_rate"  # FMPマッピング用ID

    # 発表時刻設定（ET）- 10:00 ET
    RELEASE_HOUR_ET = 10
    RELEASE_MINUTE_ET = 0

    # 発表月（四半期末60日後）
    RELEASE_MONTHS = [2, 5, 8, 11]  # 2月・5月・8月・11月

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_delinquency_rate_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        クレジットカードローン延滞率データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "qoq": float, "yoy": float}, ...],
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
            file_cache = self._load_file_cache()
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
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": None,
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
        """FRED APIからクレジットカードローン延滞率データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching Delinquency Rate from FRED...")

            # デフォルト期間（2000年から）
            if not start_date:
                start_date = "2000-01-01"

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": SERIES_ID,
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

            # 四半期比と前年比を計算
            result = self._calculate_changes(raw_data)

            print(f"Fetched {len(result)} quarterly records from FRED (Delinquency Rate)")
            return result

        except Exception as e:
            print(f"Error fetching Delinquency Rate: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _calculate_changes(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        四半期比と前年比を計算

        Args:
            raw_data: 四半期データのリスト [{"date": "YYYY-MM-DD", "value": float}, ...]

        Returns:
            [{"date": "YYYY-MM-DD", "value": float, "qoq": float, "yoy": float}, ...]
        """
        result = []

        for i, item in enumerate(raw_data):
            entry = {
                "date": item["date"],
                "value": item["value"],
                "qoq": None,  # 前四半期比（ポイント差）
                "yoy": None   # 前年比（ポイント差）
            }

            # 前四半期比（1四半期前のデータがあれば）
            if i >= 1:
                prev_value = raw_data[i - 1]["value"]
                if prev_value is not None:
                    qoq = item["value"] - prev_value
                    entry["qoq"] = round(qoq, 2)

            # 前年比（4四半期前のデータがあれば）
            if i >= 4:
                year_ago_value = raw_data[i - 4]["value"]
                if year_ago_value is not None:
                    yoy = item["value"] - year_ago_value
                    entry["yoy"] = round(yoy, 2)

            result.append(entry)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        FMPスケジュールベースの3分方式で判定
        """
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)


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
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "series_id": SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
delinquency_rate_service = DelinquencyRateService()
