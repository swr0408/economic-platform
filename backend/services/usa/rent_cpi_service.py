"""
家賃CPIサービス
Rent of Primary Residence CPI (CUUR0000SAH1) をFREDから取得

指標:
- 家賃CPI: 米国消費者物価指数の住居費部門（前年比）

データソース:
- FRED: CUUR0000SAH1 (Consumer Price Index for All Urban Consumers: Rent of primary residence)

発表スケジュール:
- BLS CPIと同時発表（毎月第2または第3週）

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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
RENT_CPI_CACHE_FILE = CACHE_DIR / "rent_cpi_cache.json"

# FRED系列ID
FRED_SERIES_ID = "CUUR0000SAH1"  # Rent of primary residence CPI


class RentCPIService:
    """家賃CPIサービス"""

    CACHE_KEY = "inflation:rent_cpi:data"
    FRED_BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_rent_cpi_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        家賃CPIデータを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "yoy": float}, ...],
                "latest": {"date": "YYYY-MM-DD", "yoy": float},
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
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # FREDからデータを取得
        rent_cpi_data = self._fetch_fred_yoy()

        if rent_cpi_data:
            latest = rent_cpi_data[-1] if rent_cpi_data else None

            cache_payload = {
                "data": rent_cpi_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": rent_cpi_data,
                "latest": latest,
                "cached": False,
                "source": "FRED",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_fred_yoy(self) -> List[Dict[str, Any]]:
        """
        FREDから家賃CPIデータを取得し、前年比を取得

        FRED APIのunits=pc1パラメータを使用して前年比を直接取得
        """
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching FRED series: {FRED_SERIES_ID} (rent_cpi)...")

            url = f"{self.FRED_BASE_URL}/series/observations"
            params = {
                "series_id": FRED_SERIES_ID,
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

            print(f"Fetched {len(result)} records for rent_cpi")
            return result

        except Exception as e:
            print(f"Error fetching rent_cpi from FRED: {e}")
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
            if not RENT_CPI_CACHE_FILE.exists():
                return None
            with open(RENT_CPI_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存する"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(RENT_CPI_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {RENT_CPI_CACHE_FILE}")
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
            "indicator": "Rent of Primary Residence CPI",
            "source": "FRED",
            "series_id": FRED_SERIES_ID,
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": RENT_CPI_CACHE_FILE.exists()
        }


# シングルトンインスタンス
rent_cpi_service = RentCPIService()
