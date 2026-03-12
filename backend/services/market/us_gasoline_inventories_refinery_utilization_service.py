"""
米国ガソリン在庫 / 製油稼働率 サービス

データソース:
  - EIA API v2: 週次データ
  - ガソリン在庫: /v2/petroleum/stoc/wstk/data/ (WGTSTUS1)
  - 製油稼働率: /v2/petroleum/sum/sndw/data/ (WPULEUS3)
  - 毎週水曜 15:30 UTC (木曜 00:30 JST)

更新: 6時間TTL (Redis + ファイル)
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
DATA_CACHE_FILE = CACHE_DIR / "us_gasoline_inventories_refinery_utilization_cache.json"

REDIS_KEY = "market:us_gasoline_inventories_refinery_utilization:data"

# Two different EIA API endpoints
GASOLINE_API_URL = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"
REFINERY_API_URL = "https://api.eia.gov/v2/petroleum/sum/sndw/data/"

GASOLINE_SERIES_ID = "WGTSTUS1"
REFINERY_SERIES_ID = "WPULEUS3"


class UsGasolineInventoriesRefineryUtilizationService:
    """EIA 米国ガソリン在庫 / 製油稼働率サービス"""

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
            logger.error(f"[GasolineRefinery] Build error: {e}")
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
            "metadata": {"source": "EIA"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        try:
            from services.usa.fmp_next_release_utils import get_next_release_from_fmp
            return get_next_release_from_fmp("us_gasoline_inventories_refinery_utilization_rate")
        except Exception as e:
            logger.error(f"[GasolineRefinery] Next release error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIA API v2から2つの系列を取得してマージ"""
        logger.info("[GasolineRefinery] Building data from EIA API v2...")

        api_key = os.environ.get("EIA_API_KEY", "")
        if not api_key:
            logger.warning("[GasolineRefinery] EIA_API_KEY not set")
            return None

        # Fetch both series
        gasoline_map = self._fetch_single_series(
            api_key, GASOLINE_API_URL, GASOLINE_SERIES_ID, "Gasoline"
        )
        refinery_map = self._fetch_single_series(
            api_key, REFINERY_API_URL, REFINERY_SERIES_ID, "Refinery"
        )

        if not gasoline_map and not refinery_map:
            logger.error("[GasolineRefinery] No data from either API")
            return None

        # Merge on date
        all_dates = sorted(set(gasoline_map.keys()) | set(refinery_map.keys()))

        result_data: List[Dict[str, Any]] = []
        for date_str in all_dates:
            gasoline_val = gasoline_map.get(date_str)
            refinery_val = refinery_map.get(date_str)

            if gasoline_val is None and refinery_val is None:
                continue

            item: Dict[str, Any] = {
                "date": date_str,
                "gasoline": gasoline_val,
                "refinery_util": round(refinery_val, 1) if refinery_val is not None else None,
            }
            result_data.append(item)

        if not result_data:
            logger.error("[GasolineRefinery] No merged data")
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[GasolineRefinery] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest gasoline={latest.get('gasoline')}, "
            f"refinery_util={latest.get('refinery_util')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "EIA",
                "frequency": "weekly",
                "series": {
                    "gasoline": "U.S. Ending Stocks of Total Gasoline (Thousand Barrels)",
                    "refinery_util": "U.S. Percent Utilization of Refinery Operable Capacity (%)",
                },
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_single_series(
        self, api_key: str, api_url: str, series_id: str, label: str
    ) -> Dict[str, float]:
        """EIA API v2から単一系列の date→value マップを取得"""
        result: Dict[str, float] = {}
        offset = 0
        length = 5000

        while True:
            try:
                resp = requests.get(api_url, params={
                    "api_key": api_key,
                    "frequency": "weekly",
                    "data[0]": "value",
                    "facets[series][]": series_id,
                    "sort[0][column]": "period",
                    "sort[0][direction]": "asc",
                    "offset": offset,
                    "length": length,
                }, timeout=30, headers={"User-Agent": "Mozilla/5.0"})

                if resp.status_code != 200:
                    logger.error(
                        f"[GasolineRefinery] {label} EIA API error: HTTP {resp.status_code}"
                    )
                    return result

                data = resp.json()
                rows = data.get("response", {}).get("data", [])
                total = int(data.get("response", {}).get("total", 0))

                for row in rows:
                    period = row.get("period", "")
                    value = row.get("value")
                    if period and value is not None:
                        try:
                            result[period] = float(value)
                        except (ValueError, TypeError):
                            pass

                logger.info(
                    f"[GasolineRefinery] {label}: fetched {len(rows)} rows "
                    f"(offset={offset}, total={total})"
                )

                if offset + len(rows) >= total or len(rows) == 0:
                    break
                offset += length

            except Exception as e:
                logger.error(f"[GasolineRefinery] {label} EIA API error: {e}")
                return result

        logger.info(f"[GasolineRefinery] {label}: total {len(result)} data points")
        return result

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[GasolineRefinery] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[GasolineRefinery] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[GasolineRefinery] Redis load error: {e}")
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
            logger.error(f"[GasolineRefinery] File load error: {e}")
        return None


us_gasoline_inventories_refinery_utilization_service = (
    UsGasolineInventoriesRefineryUtilizationService()
)
