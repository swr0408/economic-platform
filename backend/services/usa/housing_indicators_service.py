"""
住宅関連指標サービス

Zillow家賃指数、ケースシラー住宅価格指数、家賃CPIの前年比データを取得
18か月先行させて家賃CPIと比較するための指標

データソース:
- Zillow家賃指数: FRED (USAUCSFRCONDOSMSAMID)
- ケースシラー住宅価格指数: FRED (SPCS20RSA)
- 家賃CPI: FRED (CUUR0000SAH1) ※CPI項目別のshelterと同一

発表スケジュール:
- ケースシラー: 毎月最終火曜日 9:00 ET
- Zillow: 不定期

キャッシュ方式: 毎日更新（FREDデータは遅延があるため）
"""
import json
import os
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
HOUSING_INDICATORS_CACHE_FILE = CACHE_DIR / "housing_indicators_cache.json"

# FREDシリーズID
FRED_SERIES = {
    "zillow": "USAUCSFRCONDOSMSAMID",  # Zillow家賃指数
    "case_shiller": "SPCS20RSA",        # ケースシラー住宅価格指数
    "rent_cpi": "CUUR0000SAH1",         # 家賃CPI
}


class HousingIndicatorsService:
    """住宅関連指標サービス"""

    CACHE_KEY = "inflation:housing_indicators:data"
    FRED_BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_housing_indicators_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        住宅関連指標データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": {
                    "zillow": [{"date": "YYYY-MM-DD", "yoy": float}, ...],
                    "case_shiller": [{"date": "YYYY-MM-DD", "yoy": float}, ...],
                    "rent_cpi": [{"date": "YYYY-MM-DD", "yoy": float}, ...]
                },
                "latest": {
                    "zillow": {...},
                    "case_shiller": {...},
                    "rent_cpi": {...}
                },
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
                        "data": cached_data.get("data", {}),
                        "latest": cached_data.get("latest", {}),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # FREDから各指標を取得
        result_data = {}
        latest = {}

        for key, series_id in FRED_SERIES.items():
            series_data = self._fetch_fred_yoy(series_id, key)
            if series_data:
                result_data[key] = series_data
                if series_data:
                    latest[key] = series_data[-1]

        if result_data:
            cache_payload = {
                "data": result_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result_data,
                "latest": latest,
                "cached": False,
                "source": "FRED",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", {}),
                "latest": file_cache.get("latest", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": {},
            "latest": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_fred_yoy(self, series_id: str, name: str) -> List[Dict[str, Any]]:
        """
        FREDからデータを取得し、前年比を計算

        FRED APIのunits=pc1パラメータを使用して前年比を直接取得
        """
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching FRED series: {series_id} ({name})...")

            url = f"{self.FRED_BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": "2000-01-01",
                "sort_order": "asc",
                "units": "pc1"  # 前年比を直接取得
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
                            "yoy": round(float(obs["value"]), 2)
                        })
                    except (ValueError, TypeError):
                        continue

            print(f"Fetched {len(result)} records for {name}")
            return result

        except Exception as e:
            print(f"Error fetching {name} from FRED: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        FREDデータは遅延があるため、1日1回更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # 日付が変わったら更新
            if last_updated.date() < now.date():
                return True

            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not HOUSING_INDICATORS_CACHE_FILE.exists():
                return None
            with open(HOUSING_INDICATORS_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存する"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(HOUSING_INDICATORS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {HOUSING_INDICATORS_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if exists else None

        return {
            "indicator": "Housing Indicators (Zillow, Case-Shiller, Rent CPI)",
            "source": "FRED",
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_counts": {
                key: len(cached_data.get("data", {}).get(key, []))
                for key in FRED_SERIES.keys()
            } if cached_data else {},
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": HOUSING_INDICATORS_CACHE_FILE.exists()
        }


# シングルトンインスタンス
housing_indicators_service = HousingIndicatorsService()
