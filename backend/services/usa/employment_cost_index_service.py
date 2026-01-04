"""
雇用コスト指数（Employment Cost Index）サービス
FRED APIからECIALLCIV（Total Compensation）データを取得

指標:
- ECIALLCIV: Employment Cost Index: Total Compensation: All Civilian Workers

データソース:
- FRED: https://fred.stlouisfed.org/series/ECIALLCIV

発表スケジュール:
- BLS Employment Cost Index
- 四半期ごと発表（1月、4月、7月、10月）
- 発表期間: 毎月25〜31日
- 発表時刻: 21:30 (夏) / 22:30 (冬) JST

キャッシュ方式: 発表期間ベース判定方式
"""
import os
import json
from datetime import datetime
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
ET = ZoneInfo("America/New_York")

# FREDシリーズID
ECIALLCIV_SERIES_ID = "ECIALLCIV"  # Employment Cost Index: Total Compensation

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "employment_cost_index_cache.json"


class EmploymentCostIndexService:
    """雇用コスト指数サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:employment_cost_index:data"
    ECONALPHA_ID = "employment_cost_index"  # FMPマッピング用ID

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_employment_cost_index_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        雇用コスト指数データを取得（前期比）

        Returns:
            {
                "data": [{"date": str, "value": float, "pch": float}, ...],
                "latest": {...},
                "next_release": {"date": str, "label": str} | null,
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
                        "next_release": get_next_release_from_fmp('employment_cost_index'),
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
                        "next_release": get_next_release_from_fmp('employment_cost_index'),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp('employment_cost_index'),
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
                "next_release": get_next_release_from_fmp('employment_cost_index'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('employment_cost_index'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから雇用コスト指数データを取得（前期比 = pch）"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Employment Cost Index (pch) from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 前期比 (units=pch) で取得
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": ECIALLCIV_SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc",
                "units": "pch"  # 前期比
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
                    pch = float(value_str)
                    result.append({
                        "date": obs["date"],
                        "pch": round(pch, 2)  # 前期比（%）
                    })
                except (ValueError, KeyError):
                    continue

            print(f"Fetched {len(result)} Employment Cost Index records")
            return result

        except Exception as e:
            print(f"Error fetching Employment Cost Index: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load ECI file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"ECI cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save ECI file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Employment Cost Index",
            "source": "FRED / BLS",
            "series_id": ECIALLCIV_SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
employment_cost_index_service = EmploymentCostIndexService()
