"""
単位労働コスト / 労働生産性サービス
FRED APIからデータを取得

指標:
- PRS85006112: Nonfarm Business Sector: Unit Labor Costs (前期比)
- PRS85006092: Nonfarm Business Sector: Labor Productivity (前期比)

データソース:
- FRED: https://fred.stlouisfed.org/series/PRS85006112
- FRED: https://fred.stlouisfed.org/series/PRS85006092

発表スケジュール:
- BLS Productivity and Costs
- 四半期ごと発表（2月、3月、5月、6月、8月、9月、11月、12月）
- 発表期間: 毎月1〜15日
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

# FREDシリーズID
UNIT_LABOR_COSTS_SERIES_ID = "PRS85006112"  # Unit Labor Costs
LABOR_PRODUCTIVITY_SERIES_ID = "PRS85006092"  # Labor Productivity

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "unit_labor_cost_cache.json"


class UnitLaborCostService:
    """単位労働コスト / 労働生産性サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "fred:unit_labor_cost:data"
    ECONALPHA_ID = "unit_labor_cost"  # FMPマッピング用ID

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_unit_labor_cost_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        単位労働コスト / 労働生産性データを取得（前期比）

        Returns:
            {
                "data": [{"date": str, "ulc_pch": float, "productivity_pch": float}, ...],
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
                        "next_release": get_next_release_from_fmp('unit_labor_cost'),
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
                        "next_release": get_next_release_from_fmp('unit_labor_cost'),
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
                "next_release": get_next_release_from_fmp('unit_labor_cost'),
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
                "next_release": get_next_release_from_fmp('unit_labor_cost'),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp('unit_labor_cost'),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """FRED APIから単位労働コスト・労働生産性データを取得（前期比 = pch）"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return None

            print("Fetching Unit Labor Cost / Labor Productivity (pch) from FRED...")

            if not start_date:
                start_date = "2000-01-01"

            # 単位労働コスト（前期比）
            ulc_data = self._fetch_series(UNIT_LABOR_COSTS_SERIES_ID, start_date)

            # 労働生産性（前期比）
            productivity_data = self._fetch_series(LABOR_PRODUCTIVITY_SERIES_ID, start_date)

            if not ulc_data and not productivity_data:
                return None

            # データをマージ
            result = self._merge_data(ulc_data or [], productivity_data or [])

            print(f"Fetched {len(result)} Unit Labor Cost / Labor Productivity records")
            return result

        except Exception as e:
            print(f"Error fetching Unit Labor Cost data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_series(self, series_id: str, start_date: str) -> Optional[List[Dict[str, Any]]]:
        """FREDから単一シリーズのデータを取得（既に前期比）"""
        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc",
                # 注: PRS85006112/PRS85006092は既に前期比(%)なのでunitsパラメータ不要
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
                        "value": round(value, 2)
                    })
                except (ValueError, KeyError):
                    continue

            return result

        except Exception as e:
            print(f"Error fetching series {series_id}: {e}")
            return None

    def _merge_data(
        self,
        ulc_data: List[Dict[str, Any]],
        productivity_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """単位労働コストと労働生産性データをマージ"""
        date_map: Dict[str, Dict[str, Any]] = {}

        for item in ulc_data:
            date_str = item["date"]
            date_map[date_str] = {
                "date": date_str,
                "ulc_pch": item["value"],
                "productivity_pch": None
            }

        for item in productivity_data:
            date_str = item["date"]
            if date_str in date_map:
                date_map[date_str]["productivity_pch"] = item["value"]
            else:
                date_map[date_str] = {
                    "date": date_str,
                    "ulc_pch": None,
                    "productivity_pch": item["value"]
                }

        # 日付順にソート
        result = sorted(date_map.values(), key=lambda x: x["date"])
        return result

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
            print(f"Failed to load ULC file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"ULC cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save ULC file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Unit Labor Cost / Labor Productivity",
            "source": "FRED / BLS",
            "series_ids": [UNIT_LABOR_COSTS_SERIES_ID, LABOR_PRODUCTIVITY_SERIES_ID],
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
unit_labor_cost_service = UnitLaborCostService()
