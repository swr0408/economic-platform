"""
米国シェールオイル生産量 (U.S. Tight Oil Production by Formation) サービス

データソース:
  - EIA API v2 (STEO): 月次データ
  - エンドポイント: /v2/steo/data/
  - 月次データ (million barrels per day)
  - 注意: STEOのファセットキーは seriesId (他のpetroleumエンドポイントの series とは異なる)

系列:
  - TOPRL48: Total U.S. tight oil production (線グラフ)
  - TOPRAC: Austin Chalk
  - TOPRBK: Bakken
  - TOPREF: Eagle Ford
  - TOPRMP: Mississippian (→ Other に統合)
  - TOPRNI: Niobrara Codell
  - TOPRPM: Permian
  - TOPRWF: Woodford (→ Other に統合)
  - TOPRR48: Other U.S. formations (→ Other に統合)

更新スケジュール: 月次（EIA STEO発表時）
更新: 24時間TTL (Redis + ファイル)
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "us_shale_oil_production_cache.json"

REDIS_KEY = "market:us_shale_oil_production:data"

EIA_API_URL = "https://api.eia.gov/v2/steo/data/"

# Series IDs → output field names
SERIES_MAP = {
    "TOPRL48": "total",
    "TOPRAC": "austin_chalk",
    "TOPRBK": "bakken",
    "TOPREF": "eagle_ford",
    "TOPRMP": "mississippian",
    "TOPRNI": "niobrara",
    "TOPRPM": "permian",
    "TOPRWF": "woodford",
    "TOPRR48": "other",
}


class UsShaleOilProductionService:
    """米国シェールオイル生産量サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(REDIS_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() >= 6 * 3600
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                cached["next_release"] = self._get_next_release()
                return cached

        try:
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                data["next_release"] = self._get_next_release()
                return data
        except Exception as e:
            logger.error(f"[ShaleOil] Build error: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            cached["next_release"] = self._get_next_release()
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            cached["next_release"] = self._get_next_release()
            return cached

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "metadata": {"source": "EIA STEO"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        try:
            from services.usa.fmp_next_release_utils import get_next_release_from_fmp
            return get_next_release_from_fmp("weekly_crude_oil_inventories")
        except Exception as e:
            logger.error(f"[ShaleOil] Next release error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIA API v2 (STEO) からデータを取得"""
        logger.info("[ShaleOil] Building data from EIA STEO API v2...")

        api_key = os.environ.get("EIA_API_KEY", "")
        if not api_key:
            logger.warning("[ShaleOil] EIA_API_KEY not set")
            return None

        all_rows = self._fetch_from_eia(api_key)
        if not all_rows:
            return None

        # Group by date, merge series
        date_map: Dict[str, Dict[str, Any]] = {}
        for row in all_rows:
            period = row.get("period", "")
            series_id = row.get("seriesId", "")
            value = row.get("value")

            if not period or series_id not in SERIES_MAP or value is None:
                continue

            try:
                val = round(float(value), 3)
            except (ValueError, TypeError):
                continue

            # period is "YYYY-MM" → "YYYY-MM-01"
            date_str = f"{period}-01" if len(period) == 7 else period

            if date_str not in date_map:
                date_map[date_str] = {"date": date_str}
            date_map[date_str][SERIES_MAP[series_id]] = val

        result_data = sorted(date_map.values(), key=lambda x: x["date"])

        # Fill missing fields with None
        for item in result_data:
            for field in SERIES_MAP.values():
                if field not in item:
                    item[field] = None

        # Filter out rows with no total
        result_data = [d for d in result_data if d.get("total") is not None]

        if not result_data:
            logger.error("[ShaleOil] No data from EIA API")
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[ShaleOil] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest total={latest.get('total')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "EIA STEO",
                "frequency": "monthly",
                "unit": "million barrels per day",
                "series": "U.S. Tight Oil Production by Formation",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_from_eia(self, api_key: str) -> Optional[List[Dict[str, Any]]]:
        """EIA API v2 (STEO) から月次データを取得
        注意: STEOのファセットキーは seriesId (他のendpointのseriesとは異なる)
        """
        all_rows: List[Dict[str, Any]] = []
        series_ids = list(SERIES_MAP.keys())
        offset = 0
        length = 5000

        while True:
            try:
                resp = requests.get(EIA_API_URL, params={
                    "api_key": api_key,
                    "frequency": "monthly",
                    "data[0]": "value",
                    "facets[seriesId][]": series_ids,
                    "sort[0][column]": "period",
                    "sort[0][direction]": "asc",
                    "offset": offset,
                    "length": length,
                }, timeout=60, headers={"User-Agent": "Mozilla/5.0"})

                if resp.status_code != 200:
                    logger.error(f"[ShaleOil] EIA API error: HTTP {resp.status_code}")
                    return all_rows if all_rows else None

                data = resp.json()
                rows = data.get("response", {}).get("data", [])
                total = int(data.get("response", {}).get("total", 0))
                all_rows.extend(rows)

                logger.info(
                    f"[ShaleOil] Fetched {len(rows)} rows "
                    f"(offset={offset}, total={total})"
                )

                if len(all_rows) >= total or len(rows) == 0:
                    break
                offset += length

            except Exception as e:
                logger.error(f"[ShaleOil] EIA API error: {e}")
                return all_rows if all_rows else None

        logger.info(f"[ShaleOil] Total rows fetched: {len(all_rows)}")
        return all_rows

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[ShaleOil] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[ShaleOil] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[ShaleOil] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[ShaleOil] File load error: {e}")
        return None


us_shale_oil_production_service = UsShaleOilProductionService()
