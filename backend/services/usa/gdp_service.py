"""
GDP成長率 (前期比年率) サービス
FRED API (A191RL1Q225SBEA) からデータを取得

キャッシュ方式: last_updated判定（TTLなし）
更新タイミング: BEA発表スケジュールに基づいて自動更新
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FRED シリーズID
GDP_GROWTH_SERIES_ID = "A191RL1Q225SBEA"  # Real GDP Growth Rate (Quarterly, SAAR)

# ファイルキャッシュ（鮮度モニタが走査できるよう redis に加えて JSON も書く）
_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "economy"
_DATA_CACHE_FILE = _CACHE_DIR / "gdp_growth_rate_cache.json"


class GDPService:
    """GDP成長率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:gdp_growth_rate"
    # フォールバックTTL: BEA発表直後のFRED反映ラグでstaleキャッシュを掴んだ場合の救済策。
    # 発表ベースのstale判定を取りこぼしてもこの期間で必ず再取得される。
    MAX_CACHE_AGE_DAYS = 7

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def _save_file_cache(self, payload: Dict[str, Any]) -> None:
        """redis に加えて JSON ファイルにも保存（鮮度モニタの走査対象にするため）"""
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(_DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GDPService] Failed to save file cache: {e}")

    def _is_cache_expired(self, cached_data: Dict[str, Any]) -> bool:
        last_updated = cached_data.get("last_updated")
        if not last_updated:
            return True
        try:
            last_dt = datetime.fromisoformat(last_updated)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=JST)
            age = datetime.now(JST) - last_dt
            return age.total_seconds() > self.MAX_CACHE_AGE_DAYS * 86400
        except Exception:
            return True

    def fetch_gdp_growth_rate(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        GDP成長率（前期比年率）を取得

        FRED Series: A191RL1Q225SBEA
        - Real Gross Domestic Product
        - Percent Change from Preceding Period
        - Seasonally Adjusted Annual Rate (SAAR)

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック（7日経過したらフォールバックで再取得）
        cached_data = redis_client.get(self.CACHE_KEY)
        if not force_refresh and cached_data and not self._is_cache_expired(cached_data):
            return {
                "data": cached_data.get("data", []),
                "cached": True,
                "source": "redis",
                "last_updated": cached_data.get("last_updated")
            }

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date, end_date)

        if api_data:
            cache_payload = {
                "data": api_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（last_updated判定方式）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # API失敗時: 期限切れでも既存キャッシュを返す（データ欠落防止）
        if cached_data:
            return {
                "data": cached_data.get("data", []),
                "cached": True,
                "source": "redis_stale",
                "last_updated": cached_data.get("last_updated")
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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """FRED APIからGDP成長率データを取得"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching GDP growth rate from FRED ({GDP_GROWTH_SERIES_ID})...")

            # デフォルト期間（1990年から）
            if not start_date:
                start_date = "1990-01-01"
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": GDP_GROWTH_SERIES_ID,
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
                            "value": round(float(obs["value"]), 2)
                        })
                    except (ValueError, TypeError):
                        continue

            print(f"Fetched {len(result)} GDP growth rate records from FRED")
            return result

        except Exception as e:
            print(f"Error fetching GDP growth rate from FRED: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_gdp_growth_rate(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        GDP成長率データを取得（エイリアス）

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        return self.fetch_gdp_growth_rate(force_refresh=force_refresh)

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "series_id": GDP_GROWTH_SERIES_ID,
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,  # -1 = TTLなし
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "record_count": len(cached_data.get("data", [])) if cached_data else 0
        }

    def get_latest_value(self) -> Optional[Dict[str, Any]]:
        """
        最新のGDP成長率を取得

        Returns:
            {"date": "YYYY-MM-DD", "value": float} or None
        """
        result = self.get_gdp_growth_rate()
        data = result.get("data", [])
        return data[-1] if data else None


# シングルトンインスタンス
gdp_service = GDPService()
