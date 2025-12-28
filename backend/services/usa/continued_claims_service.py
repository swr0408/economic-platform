"""
継続失業保険申請件数（UI Continued Claims）サービス
FRED APIから継続失業保険申請件数データを取得

指標:
- CCSA: Continued Claims, Weekly, Seasonally Adjusted
- CC4WSA: 4-Week Moving Average of Continued Claims, Weekly, Seasonally Adjusted

データソース:
- FRED: https://fred.stlouisfed.org/series/CCSA
- DOL: https://oui.doleta.gov/unemploy/claims_arch.asp

発表スケジュール:
- 毎週木曜日 8:30 AM ET（新規失業保険申請件数と同時発表）
- 祝日による例外日あり（DOLサイトからスクレイピング、月1回更新）

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
from services.usa.release_schedule_utils import WEEKLY_CLAIMS_CHECKER


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
CCSA_SERIES_ID = "CCSA"         # 継続失業保険申請件数
CC4WSA_SERIES_ID = "CC4WSA"     # 4週移動平均

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "continued_claims_cache.json"


class ContinuedClaimsService:
    """継続失業保険申請件数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:continued_claims:data"

    # 発表時刻設定（ET）- 8:30 AM ET（新規失業保険申請件数と同時）
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 30

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self.schedule_checker = WEEKLY_CLAIMS_CHECKER

    def get_continued_claims_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        継続失業保険申請件数データを取得

        Returns:
            {
                "data": [{"date": str, "ccsa": float, "cc4wsa": float}, ...],
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
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        ccsa_data = self._fetch_series_from_api(CCSA_SERIES_ID, start_date)
        cc4wsa_data = self._fetch_series_from_api(CC4WSA_SERIES_ID, start_date)

        if ccsa_data:
            # データを結合
            combined_data = self._combine_data(ccsa_data, cc4wsa_data)
            latest = combined_data[-1] if combined_data else None

            cache_payload = {
                "data": combined_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": combined_data,
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

    def _fetch_series_from_api(self, series_id: str, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから指定シリーズのデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print(f"Fetching {series_id} from FRED...")

            if not start_date:
                start_date = "2000-01-01"

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
                        "value": round(value, 0)  # 実数（件）
                    })
                except (ValueError, KeyError):
                    continue

            print(f"Fetched {len(result)} {series_id} records")
            return result

        except Exception as e:
            print(f"Error fetching {series_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _combine_data(
        self,
        ccsa_data: List[Dict[str, Any]],
        cc4wsa_data: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """CCSAとCC4WSAのデータを結合"""
        # CCSAをベースにする
        ccsa_map = {d["date"]: d["value"] for d in ccsa_data}

        # CC4WSAをマップに変換
        cc4wsa_map = {}
        if cc4wsa_data:
            cc4wsa_map = {d["date"]: d["value"] for d in cc4wsa_data}

        # 全ての日付を取得
        all_dates = sorted(set(ccsa_map.keys()) | set(cc4wsa_map.keys()))

        result = []
        for dt in all_dates:
            ccsa_value = ccsa_map.get(dt)
            cc4wsa_value = cc4wsa_map.get(dt)

            if ccsa_value is not None:  # CCSAがある場合のみ含める
                result.append({
                    "date": dt,
                    "ccsa": ccsa_value,
                    "cc4wsa": cc4wsa_value
                })

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return self.schedule_checker.should_refresh(last_updated_str)

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
            print(f"Continued Claims cache saved to {DATA_CACHE_FILE}")
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
            "indicator": "Continued Claims (UI Weekly Claims)",
            "source": "FRED / DOL",
            "series_ids": [CCSA_SERIES_ID, CC4WSA_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "schedule_status": self.schedule_checker.get_status(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
continued_claims_service = ContinuedClaimsService()
