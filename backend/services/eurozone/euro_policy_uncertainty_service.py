"""
欧州経済政策不確実性指数サービス
FREDから European Policy Uncertainty Index データを取得

指標:
- European Policy Uncertainty Index
- FRED シリーズID: EUEPUINDXM

データソース:
- FRED (Federal Reserve Economic Data)
- 元データ: Economic Policy Uncertainty Project (policyuncertainty.com)

発表スケジュール:
- 日次更新（毎日 2:00 JST）

キャッシュ方式: 24時間固定TTL方式（FMP非対応のため）
"""
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "euro_policy_uncertainty_cache.json"


class EuroPolicyUncertaintyService:
    """欧州経済政策不確実性指数サービス"""

    DATA_CACHE_KEY = "eurozone:policy_uncertainty:data"
    SERIES_ID = "EUEPUINDXM"
    FRED_BASE_URL = "https://api.stlouisfed.org/fred"
    DEFAULT_START_DATE = "2000-01-01"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_euro_policy_uncertainty_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """欧州政策不確実性指数データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # FRED APIから取得
        api_result = self._fetch_from_fred()
        if api_result:
            latest = api_result[-1] if api_result else None

            cache_payload = {
                "data": api_result,
                "latest": latest,
                "metadata": {
                    "source": "FRED (Federal Reserve Economic Data)",
                    "series_id": self.SERIES_ID,
                    "indicator": "European Economic Policy Uncertainty Index",
                    "unit": "Index",
                    "frequency": "Monthly",
                    "description": "News-based index of economic policy uncertainty for Europe",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "cached": False,
                "source": "fred_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_fred(self) -> Optional[List[Dict]]:
        """FRED APIからデータを取得"""
        try:
            if not self.api_key:
                print("[EuroPolicyUncertainty] FRED_API_KEY not set")
                return None

            print(f"[EuroPolicyUncertainty] Fetching {self.SERIES_ID} from FRED...")

            url = f"{self.FRED_BASE_URL}/series/observations"
            params = {
                "series_id": self.SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": self.DEFAULT_START_DATE,
                "sort_order": "asc",
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            observations = data.get("observations", [])
            result = []

            for obs in observations:
                if obs.get("value") and obs["value"] != ".":
                    try:
                        # 日付を月初日に正規化 (YYYY-MM-01)
                        date_str = obs["date"][:7] + "-01"
                        value = round(float(obs["value"]), 2)

                        result.append({
                            "date": date_str,
                            "value": value,
                        })
                    except (ValueError, TypeError):
                        continue

            print(f"[EuroPolicyUncertainty] Fetched {len(result)} records from FRED")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EuroPolicyUncertainty] Request error: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            print(f"[EuroPolicyUncertainty] Parse error: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（毎日更新方式）
        毎日2:00 JST以降に更新チェック（24時間TTL）
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 24時間経過していれば更新
            if (now - last_updated) > timedelta(hours=24):
                return True

            # 日付が変わっており、かつ2:00を過ぎていれば更新
            if last_updated.date() < now.date() and now.hour >= 2:
                return True

            return False
        except Exception as e:
            print(f"[EuroPolicyUncertainty] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[EuroPolicyUncertainty] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EuroPolicyUncertainty] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "European Policy Uncertainty Index",
            "source": "FRED",
            "series_id": self.SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
euro_policy_uncertainty_service = EuroPolicyUncertaintyService()
