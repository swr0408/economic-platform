"""
週間原油在庫 (EIA Weekly Crude Oil Inventories) サービス

データソース:
  - EIA API v2: 週次データ
  - エンドポイント: /v2/petroleum/stoc/wstk/data/
  - 毎週水曜 15:30 UTC (木曜 00:30 JST)

3系列:
  - WCRSTUS1: 原油在庫合計 (千バレル)
  - WCESTUS1: 原油在庫 SPR除く (千バレル)
  - WCSSTUS1: SPR在庫 (千バレル)

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "weekly_crude_oil_inventories_cache.json"

REDIS_KEY = "market:weekly_crude_oil_inventories:data"

EIA_API_URL = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"

# Target series IDs and their field names
TARGET_SERIES = {
    "WCRSTUS1": "total",       # Crude Oil Total (incl SPR)
    "WCESTUS1": "ex_spr",      # Crude Oil excl SPR (commercial)
    "WCSSTUS1": "spr",         # SPR only
}


class WeeklyCrudeOilInventoriesService:
    """EIA 週間原油在庫サービス"""

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
            logger.error(f"[CrudeOilInv] Build error: {e}")
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
        """FMPから次回EIA原油在庫発表日を取得"""
        try:
            from services.usa.fmp_next_release_utils import get_next_release_from_fmp
            return get_next_release_from_fmp("weekly_crude_oil_inventories")
        except Exception as e:
            logger.error(f"[CrudeOilInv] Next release error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIA API v2からデータを取得"""
        logger.info("[CrudeOilInv] Building data from EIA API v2...")

        api_key = os.environ.get("EIA_API_KEY", "")
        if not api_key:
            logger.warning("[CrudeOilInv] EIA_API_KEY not set")
            return None

        # Fetch all 3 series in one request
        series_ids = list(TARGET_SERIES.keys())
        all_rows = self._fetch_from_eia(api_key, series_ids)
        if not all_rows:
            return None

        # Group by date, merge series
        date_map: Dict[str, Dict[str, Any]] = {}
        for row in all_rows:
            period = row.get("period", "")
            series = row.get("series", "")
            value = row.get("value")

            if not period or series not in TARGET_SERIES or value is None:
                continue

            try:
                val = round(float(value), 0)
            except (ValueError, TypeError):
                continue

            field = TARGET_SERIES[series]
            if period not in date_map:
                date_map[period] = {"date": period}
            date_map[period][field] = val

        result_data = sorted(date_map.values(), key=lambda x: x["date"])

        # Fill missing fields with None
        for item in result_data:
            for field in TARGET_SERIES.values():
                if field not in item:
                    item[field] = None

        # Skip rows with no values
        result_data = [
            d for d in result_data
            if any(d.get(f) is not None for f in TARGET_SERIES.values())
        ]

        if not result_data:
            logger.error("[CrudeOilInv] No data from EIA API")
            return None

        # Calculate YoY (前年比) for each series
        date_idx_map = {d["date"]: i for i, d in enumerate(result_data)}
        for i, item in enumerate(result_data):
            for field in TARGET_SERIES.values():
                val = item.get(field)
                if val is None:
                    item[f"{field}_yoy"] = None
                    continue

                current_date = datetime.strptime(item["date"], "%Y-%m-%d")
                target_date = current_date - timedelta(days=364)

                best_match = None
                best_diff = 999
                for offset_days in range(-7, 8):
                    check_date = target_date + timedelta(days=offset_days)
                    check_str = check_date.strftime("%Y-%m-%d")
                    if check_str in date_idx_map:
                        diff = abs(offset_days)
                        if diff < best_diff:
                            best_diff = diff
                            best_match = date_idx_map[check_str]

                if best_match is not None:
                    prev_val = result_data[best_match].get(field)
                    if prev_val and prev_val != 0:
                        yoy_pct = ((val - prev_val) / prev_val) * 100
                        item[f"{field}_yoy"] = round(yoy_pct, 2)
                    else:
                        item[f"{field}_yoy"] = None
                else:
                    item[f"{field}_yoy"] = None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[CrudeOilInv] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest total={latest.get('total')}, "
            f"ex_spr={latest.get('ex_spr')}, spr={latest.get('spr')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "EIA",
                "frequency": "weekly",
                "unit": "Thousand Barrels",
                "series": {
                    "total": "U.S. Ending Stocks of Crude Oil (incl SPR)",
                    "ex_spr": "U.S. Ending Stocks excluding SPR",
                    "spr": "U.S. Ending Stocks in SPR",
                },
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_from_eia(
        self, api_key: str, series_ids: List[str]
    ) -> Optional[List[Dict[str, Any]]]:
        """EIA API v2から週次データを取得（ページネーション対応）"""
        all_rows: List[Dict[str, Any]] = []
        offset = 0
        length = 5000

        while True:
            params: Dict[str, Any] = {
                "api_key": api_key,
                "frequency": "weekly",
                "data[0]": "value",
                "sort[0][column]": "period",
                "sort[0][direction]": "asc",
                "offset": offset,
                "length": length,
            }
            for i, sid in enumerate(series_ids):
                params[f"facets[series][]"] = series_ids

            try:
                resp = requests.get(EIA_API_URL, params={
                    "api_key": api_key,
                    "frequency": "weekly",
                    "data[0]": "value",
                    "facets[series][]": series_ids,
                    "sort[0][column]": "period",
                    "sort[0][direction]": "asc",
                    "offset": offset,
                    "length": length,
                }, timeout=30, headers={"User-Agent": "Mozilla/5.0"})

                if resp.status_code != 200:
                    logger.error(f"[CrudeOilInv] EIA API error: HTTP {resp.status_code}")
                    return all_rows if all_rows else None

                data = resp.json()
                rows = data.get("response", {}).get("data", [])
                total = int(data.get("response", {}).get("total", 0))

                all_rows.extend(rows)
                logger.info(
                    f"[CrudeOilInv] Fetched {len(rows)} rows "
                    f"(offset={offset}, total={total})"
                )

                if len(all_rows) >= total or len(rows) == 0:
                    break
                offset += length

            except Exception as e:
                logger.error(f"[CrudeOilInv] EIA API error: {e}")
                return all_rows if all_rows else None

        logger.info(f"[CrudeOilInv] Total rows fetched: {len(all_rows)}")
        return all_rows

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[CrudeOilInv] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[CrudeOilInv] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[CrudeOilInv] Redis load error: {e}")
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
            logger.error(f"[CrudeOilInv] File load error: {e}")
        return None


weekly_crude_oil_inventories_service = WeeklyCrudeOilInventoriesService()
