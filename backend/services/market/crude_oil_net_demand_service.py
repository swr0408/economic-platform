"""
米国 原油純需要 (Crude Oil Net Demand) サービス

データソース:
  - EIA API v2: 週次データ
  - エンドポイント: /v2/petroleum/sum/sndw/data/
  - WRPUPUS2: Total Petroleum Products Supplied (千bbl/日)
  - WCRFPUS2: U.S. Field Production of Crude Oil (千bbl/日)
  - Net Demand = Products Supplied - Field Production

計算:
  - net_demand: WRPUPUS2 - WCRFPUS2 (千bbl/日)
  - ma4: 4週移動平均
  - yoy: 純需要の生前年比 (52週前±7日のfuzzyマッチ)
  - ma4_yoy: 生YoYの4週移動平均

更新スケジュール: 週次（EIA原油在庫と同タイミング）
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
DATA_CACHE_FILE = CACHE_DIR / "crude_oil_net_demand_cache.json"

REDIS_KEY = "market:crude_oil_net_demand:data"

EIA_API_URL = "https://api.eia.gov/v2/petroleum/sum/sndw/data/"

# Series IDs (Weekly Petroleum Supply)
PRODUCT_SUPPLIED_SERIES = "WRPUPUS2"  # Total Petroleum Products Supplied (千bbl/日)
FIELD_PRODUCTION_SERIES = "WCRFPUS2"  # U.S. Field Production of Crude Oil (千bbl/日)


class CrudeOilNetDemandService:
    """米国 原油純需要サービス"""

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
            logger.error(f"[NetDemand] Build error: {e}")
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
            return get_next_release_from_fmp("weekly_crude_oil_inventories")
        except Exception as e:
            logger.error(f"[NetDemand] Next release error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIA API v2 週次石油供給データから純需要を算出"""
        logger.info("[NetDemand] Building data from EIA API v2 (petroleum/sum/sndw)...")

        api_key = os.environ.get("EIA_API_KEY", "")
        if not api_key:
            logger.warning("[NetDemand] EIA_API_KEY not set")
            return None

        all_rows = self._fetch_from_eia(api_key)
        if not all_rows:
            return None

        # Group by date
        supplied_map: Dict[str, float] = {}
        production_map: Dict[str, float] = {}

        for row in all_rows:
            period = row.get("period", "")
            series = row.get("series", "")
            value = row.get("value")

            if not period or value is None:
                continue

            try:
                val = round(float(value), 1)
            except (ValueError, TypeError):
                continue

            if series == PRODUCT_SUPPLIED_SERIES:
                supplied_map[period] = val
            elif series == FIELD_PRODUCTION_SERIES:
                production_map[period] = val

        # Merge: net_demand = products_supplied - field_production
        all_dates = sorted(set(supplied_map.keys()) & set(production_map.keys()))

        result_data: List[Dict[str, Any]] = []
        for date_str in all_dates:
            supplied = supplied_map[date_str]
            production = production_map[date_str]
            net = round(supplied - production, 1)
            result_data.append({
                "date": date_str,
                "products_supplied": supplied,
                "field_production": production,
                "net_demand": net,
            })

        if not result_data:
            logger.error("[NetDemand] No data from EIA API")
            return None

        # Calculate 4-week moving average
        for i, item in enumerate(result_data):
            if i >= 3:
                vals = [result_data[j]["net_demand"] for j in range(i - 3, i + 1)]
                item["ma4"] = round(sum(vals) / 4, 1)
            else:
                item["ma4"] = None

        # Calculate raw YoY (方式A: 生前年比, 52週前±7日のfuzzyマッチ)
        date_idx_map = {d["date"]: i for i, d in enumerate(result_data)}
        for item in result_data:
            net_val = item.get("net_demand")
            if net_val is None:
                item["yoy"] = None
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
                prev_net = result_data[best_match].get("net_demand")
                if prev_net is not None and prev_net != 0:
                    yoy_pct = ((net_val - prev_net) / abs(prev_net)) * 100
                    item["yoy"] = round(yoy_pct, 2)
                else:
                    item["yoy"] = None
            else:
                item["yoy"] = None

        # Calculate 4-week MA of raw YoY (方式C: 生YoYの4週移動平均)
        for i, item in enumerate(result_data):
            if i >= 3:
                yoy_vals = [result_data[j].get("yoy") for j in range(i - 3, i + 1)]
                if all(v is not None for v in yoy_vals):
                    item["ma4_yoy"] = round(sum(yoy_vals) / 4, 2)  # type: ignore
                else:
                    item["ma4_yoy"] = None
            else:
                item["ma4_yoy"] = None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[NetDemand] {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest net_demand={latest.get('net_demand')}, ma4={latest.get('ma4')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "EIA",
                "frequency": "weekly",
                "unit": "Thousand Barrels per Day",
                "series": {
                    "products_supplied": "U.S. Total Petroleum Products Supplied (WRPUPUS2)",
                    "field_production": "U.S. Field Production of Crude Oil (WCRFPUS2)",
                    "net_demand": "Products Supplied - Field Production",
                    "ma4": "4-Week Moving Average of Net Demand",
                    "yoy": "Net Demand Raw Year-over-Year %",
                    "ma4_yoy": "4-Week MA of Raw YoY %",
                },
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _fetch_from_eia(self, api_key: str) -> Optional[List[Dict[str, Any]]]:
        """EIA API v2 週次石油供給データを取得"""
        all_rows: List[Dict[str, Any]] = []
        series_ids = [PRODUCT_SUPPLIED_SERIES, FIELD_PRODUCTION_SERIES]
        offset = 0
        length = 5000

        while True:
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
                }, timeout=60, headers={"User-Agent": "Mozilla/5.0"})

                if resp.status_code != 200:
                    logger.error(f"[NetDemand] EIA API error: HTTP {resp.status_code}")
                    return all_rows if all_rows else None

                data = resp.json()
                rows = data.get("response", {}).get("data", [])
                total = int(data.get("response", {}).get("total", 0))
                all_rows.extend(rows)

                logger.info(
                    f"[NetDemand] Fetched {len(rows)} rows "
                    f"(offset={offset}, total={total})"
                )

                if len(all_rows) >= total or len(rows) == 0:
                    break
                offset += length

            except Exception as e:
                logger.error(f"[NetDemand] EIA API error: {e}")
                return all_rows if all_rows else None

        logger.info(f"[NetDemand] Total rows fetched: {len(all_rows)}")
        return all_rows

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NetDemand] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[NetDemand] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NetDemand] Redis load error: {e}")
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
            logger.error(f"[NetDemand] File load error: {e}")
        return None


crude_oil_net_demand_service = CrudeOilNetDemandService()
