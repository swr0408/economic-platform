"""
FRED (Federal Reserve Economic Data) API サービス
KWタームプレミアム（THREEFYTP10）取得用
"""
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests

from core.redis_client import redis_client, CACHE_TTL_LONG


class FREDService:
    """FRED API サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_TTL = CACHE_TTL_LONG

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def _get_cache_key(self, series_id: str) -> str:
        return f"fred:series:{series_id}"

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        FREDシリーズデータを取得

        Args:
            series_id: シリーズID (例: "THREEFYTP10")
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [...],
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        cache_key = self._get_cache_key(series_id)

        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                return {
                    "data": cached_data.get("data", []),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # 外部APIから取得
        api_data = self._fetch_from_api(series_id, start_date, end_date)

        if api_data:
            cache_payload = {
                "data": api_data,
                "last_updated": datetime.now().isoformat()
            }
            redis_client.set(cache_key, cache_payload, expire=self.CACHE_TTL)

            return {
                "data": api_data,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now().isoformat()
            }

        return {
            "data": [],
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """FRED APIからデータを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching FRED series: {series_id}...")

            # デフォルト期間（1990年から）
            if not start_date:
                start_date = "1990-01-01"
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "observation_end": end_date,
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

            print(f"Fetched {len(result)} records from FRED ({series_id})")
            return result

        except Exception as e:
            print(f"Error fetching from FRED: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_kw_term_premium(self, force_refresh: bool = False) -> Dict[str, Any]:
        """KWモデル タームプレミアム（THREEFYTP10）を取得"""
        return self.fetch_series("THREEFYTP10", force_refresh=force_refresh)

    def get_policy_rate(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        政策金利（Federal Funds Target Rate Upper Bound - DFEDTARU）を取得

        FRED Series: DFEDTARU
        Source: https://fred.stlouisfed.org/series/DFEDTARU

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "rate": float}, ...],
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        result = self.fetch_series("DFEDTARU", start_date="2003-01-01", force_refresh=force_refresh)

        # valueをrateにリネーム（既存APIとの互換性のため）
        if result.get("data"):
            result["data"] = [
                {"date": item["date"], "rate": item["value"]}
                for item in result["data"]
            ]

        return result

    def invalidate_cache(self, series_id: str) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self._get_cache_key(series_id))

    def get_cache_status(self, series_id: str) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_key = self._get_cache_key(series_id)
        cache_exists = redis_client.exists(cache_key)
        ttl = redis_client.ttl(cache_key) if cache_exists else -1

        return {
            "series_id": series_id,
            "cache_key": cache_key,
            "exists": cache_exists,
            "ttl_seconds": ttl,
            "ttl_hours": round(ttl / 3600, 2) if ttl > 0 else 0
        }


# シングルトンインスタンス
fred_service = FREDService()
