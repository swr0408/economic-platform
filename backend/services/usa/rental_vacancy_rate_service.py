"""
賃貸空室率サービス

FREDから賃貸空室率 (RRVRUSQ156N) を取得

指標:
- 賃貸空室率（四半期）

データソース:
- FRED: RRVRUSQ156N (Rental Vacancy Rate)

発表スケジュール:
- 四半期（不定期）
- https://www.census.gov/housing/hvs/data/upcoming.html

キャッシュ方式: 独自判定方式（FMP非対応）
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class RentalVacancyRateService:
    """賃貸空室率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"

    # シリーズID
    SERIES_ID = "RRVRUSQ156N"

    # キャッシュキー
    DATA_CACHE_KEY = "housing:rental_vacancy_rate:data"
    DATA_CACHE_FILE = CACHE_DIR / "rental_vacancy_rate_cache.json"

    # デフォルトの開始日
    DEFAULT_START_DATE = "2000-01-01"

    # キャッシュ有効期間（24時間）
    CACHE_TTL_HOURS = 24

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_rental_vacancy_rate_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        賃貸空室率データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            {
                "data": [{date, value}, ...],
                "latest": {...},
                "next_release": {...},
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
                        "next_release": self._get_next_release_info(),
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
                        "next_release": self._get_next_release_info(),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FREDからデータを取得
        raw_data = self._fetch_from_fred()

        if raw_data:
            latest = raw_data[-1] if raw_data else None

            cache_payload = {
                "data": raw_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }

            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": raw_data,
                "latest": latest,
                "next_release": self._get_next_release_info(),
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # フォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": self._get_next_release_info(),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": self._get_next_release_info(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_fred(self) -> List[Dict[str, Any]]:
        """FREDからデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching {self.SERIES_ID} from FRED...")

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": self.SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": self.DEFAULT_START_DATE,
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

            print(f"Fetched {len(result)} records from FRED ({self.SERIES_ID})")
            return result

        except Exception as e:
            print(f"Error fetching {self.SERIES_ID}: {e}")
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（24時間経過で更新）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            hours_elapsed = (now - last_updated).total_seconds() / 3600
            return hours_elapsed >= self.CACHE_TTL_HOURS
        except Exception:
            return True

    def _get_next_release_info(self) -> Optional[Dict[str, Any]]:
        """次回発表情報を返す（Census Bureauのスケジュールページ参照）"""
        return {
            "note": "四半期データ - Census Bureau Housing Vacancies and Homeownership",
            "schedule_url": "https://www.census.gov/housing/hvs/data/upcoming.html"
        }

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not self.DATA_CACHE_FILE.exists():
                return None
            with open(self.DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {self.DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Rental Vacancy Rate",
            "source": "FRED",
            "series_id": self.SERIES_ID,
            "cache_method": "24時間TTL",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "next_release": self._get_next_release_info(),
            "file_cache_exists": self.DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
rental_vacancy_rate_service = RentalVacancyRateService()
