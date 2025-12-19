"""
潜在成長率サービス
FRED APIから名目/実質潜在GDPを取得し、前年比成長率を算出

シリーズID:
- GDPPOT: 実質潜在GDP (Billions of Chained 2017 Dollars)
- NGDPPOT: 名目潜在GDP (Billions of Dollars)

キャッシュ方式: TTL（日本時間6:00に更新）
更新タイミング: CBO/FREDの発表に基づいて自動更新
"""
import os
from datetime import datetime, time
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from core.redis_client import redis_client

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FRED シリーズID
REAL_POTENTIAL_GDP_SERIES_ID = "GDPPOT"    # Real Potential GDP
NOMINAL_POTENTIAL_GDP_SERIES_ID = "NGDPPOT"  # Nominal Potential GDP


class PotentialGDPService:
    """潜在成長率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:potential_gdp"
    CACHE_TTL_SECONDS = 24 * 60 * 60  # 24時間（日本時間6:00に更新するためTTLで管理）

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def fetch_potential_gdp(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        名目/実質潜在成長率を取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "real": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "nominal": [{"date": "YYYY-MM-DD", "value": float}, ...],
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
                    "real": cached_data.get("real", []),
                    "nominal": cached_data.get("nominal", []),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # 外部APIから並列で取得
        api_data = self._fetch_all_series(start_date)

        if api_data:
            cache_payload = {
                "real": api_data["real"],
                "nominal": api_data["nominal"],
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLあり（日本時間6:00に更新）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=self.CACHE_TTL_SECONDS)

            return {
                "real": api_data["real"],
                "nominal": api_data["nominal"],
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "real": [],
            "nominal": [],
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_all_series(
        self,
        start_date: Optional[str] = None
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """名目・実質潜在GDPを並列で取得し、前年比成長率を算出"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            # デフォルト期間（1990年から）
            if not start_date:
                start_date = "1990-01-01"

            print(f"Fetching Potential GDP from FRED...")

            result = {}

            # 並列で取得
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(
                        self._fetch_single_series_with_growth,
                        REAL_POTENTIAL_GDP_SERIES_ID,
                        start_date
                    ): "real",
                    executor.submit(
                        self._fetch_single_series_with_growth,
                        NOMINAL_POTENTIAL_GDP_SERIES_ID,
                        start_date
                    ): "nominal",
                }

                for future in as_completed(futures):
                    key = futures[future]
                    try:
                        result[key] = future.result()
                    except Exception as e:
                        print(f"Error fetching {key} potential GDP: {e}")
                        result[key] = []

            print(f"Fetched {len(result.get('real', []))} real and {len(result.get('nominal', []))} nominal potential GDP records")
            return result

        except Exception as e:
            print(f"Error fetching potential GDP: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_single_series_with_growth(
        self,
        series_id: str,
        start_date: str
    ) -> List[Dict[str, Any]]:
        """
        単一シリーズを取得し、前年比成長率（pc1）を算出

        FREDのunits=pc1を使用して前年比変化率を取得
        """
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                # observation_endを指定しない（CBOの予測データは2035年まであるため）
                "sort_order": "asc",
                "units": "pc1"  # Percent Change from Year Ago
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

    def get_potential_gdp(self, force_refresh: bool = False) -> Dict[str, Any]:
        """潜在成長率データを取得（エイリアス）"""
        return self.fetch_potential_gdp(force_refresh=force_refresh)

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "series_ids": {
                "real": REAL_POTENTIAL_GDP_SERIES_ID,
                "nominal": NOMINAL_POTENTIAL_GDP_SERIES_ID
            },
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "real_count": len(cached_data.get("real", [])) if cached_data else 0,
            "nominal_count": len(cached_data.get("nominal", [])) if cached_data else 0
        }

    def get_latest_values(self) -> Optional[Dict[str, Any]]:
        """
        最新の潜在成長率を取得

        Returns:
            {
                "real": {"date": "YYYY-MM-DD", "value": float},
                "nominal": {"date": "YYYY-MM-DD", "value": float}
            }
        """
        result = self.get_potential_gdp()
        real_data = result.get("real", [])
        nominal_data = result.get("nominal", [])

        return {
            "real": real_data[-1] if real_data else None,
            "nominal": nominal_data[-1] if nominal_data else None
        }


# シングルトンインスタンス
potential_gdp_service = PotentialGDPService()
