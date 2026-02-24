"""
Australian Bureau of Statistics (ABS) 家計支出（Household Spending）サービス

データソース:
- ABS SDMX API (HSI_M dataflow)
- MEASURE 8 = Percentage change from previous period (MoM%)
- MEASURE 9 = Through the year percentage change (YoY%)
- Category: Total (TOT), Current Price, Seasonally Adjusted (20)
- Region: Australia (AUS), Frequency: Monthly (M)

発表スケジュール: 月次
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_household_spending_cache.json"

# ABS API設定
ABS_API_BASE = "https://data.api.abs.gov.au/rest/data"
HSI_DATAFLOW = "ABS,HSI_M,"
HSI_KEY = "8+9.TOT..20.AUS.M"
HSI_URL = f"{ABS_API_BASE}/{HSI_DATAFLOW}/{HSI_KEY}?startPeriod=2017-01&dimensionAtObservation=AllDimensions"

FMP_EVENT_PATTERNS = ["Household Spending MoM", "Household Spending YoY"]


class AuHouseholdSpendingService:
    """ABS Household Spending Service"""

    DATA_CACHE_KEY = "australia:au_household_spending:data"

    def __init__(self):
        pass

    def _fetch_sdmx(self, url: str) -> Optional[Dict[str, Any]]:
        """ABS SDMX APIからデータを取得"""
        try:
            logger.info(f"Fetching ABS HSI data from {url}")
            response = requests.get(
                url,
                headers={
                    "Accept": "application/vnd.sdmx.data+json",
                    "User-Agent": "Mozilla/5.0 (economic-platform)",
                },
                timeout=30,
            )
            if response.status_code != 200:
                logger.error(f"ABS API returned HTTP {response.status_code} for {url}")
                return None
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching ABS HSI data: {e}")
            return None

    def _parse_sdmx_observations(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """SDMX JSONレスポンスをパースしてデータポイントを構築"""
        result = []
        try:
            datasets = raw_data.get("data", {}).get("dataSets", [])
            if not datasets:
                return []
            observations = datasets[0].get("observations", {})
            if not observations:
                return []
            structures = raw_data.get("data", {}).get("structures", [])
            if not structures:
                return []
            dimensions = structures[0].get("dimensions", {}).get("observation", [])
            dim_lookups = {}
            for dim in dimensions:
                dim_id = dim.get("id", "")
                values = dim.get("values", [])
                dim_lookups[dim_id] = {str(i): v.get("id", "") for i, v in enumerate(values)}
            dim_ids = [d.get("id", "") for d in dimensions]

            for obs_key, obs_value in observations.items():
                if obs_value is None or obs_value[0] is None:
                    continue
                value = obs_value[0]
                indices = obs_key.split(":")
                codes = {}
                for i, idx in enumerate(indices):
                    if i < len(dim_ids):
                        dim_id = dim_ids[i]
                        lookup = dim_lookups.get(dim_id, {})
                        codes[dim_id] = lookup.get(idx, idx)
                result.append({
                    "measure": codes.get("MEASURE", ""),
                    "time_period": codes.get("TIME_PERIOD", ""),
                    "value": value,
                })
        except Exception as e:
            logger.error(f"Error parsing SDMX HSI data: {e}")
        return result

    def _month_to_date(self, month_str: str) -> str:
        """'2025-12' -> '2025-12-01'"""
        return f"{month_str}-01" if len(month_str) == 7 else month_str

    def _build_data_points(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """観測データからMoM/YoYを結合したデータポイントを構築"""
        period_data: Dict[str, Dict[str, float]] = {}
        for obs in observations:
            tp = obs.get("time_period", "")
            measure = obs.get("measure", "")
            if not tp:
                continue
            if tp not in period_data:
                period_data[tp] = {}
            # MEASURE 8 = MoM%, MEASURE 9 = YoY%
            if measure == "8":
                period_data[tp]["mom"] = round(obs["value"], 2)
            elif measure == "9":
                period_data[tp]["yoy"] = round(obs["value"], 2)

        data_points = []
        for tp, values in period_data.items():
            data_points.append({
                "date": self._month_to_date(tp),
                "mom": values.get("mom"),
                "yoy": values.get("yoy"),
            })
        data_points.sort(key=lambda x: x["date"])
        logger.info(f"Built {len(data_points)} Household Spending data points")
        return data_points

    def get_au_household_spending_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """家計支出データを取得（キャッシュ付き）"""
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                    }

        raw_data = self._fetch_sdmx(HSI_URL)
        if raw_data:
            observations = self._parse_sdmx_observations(raw_data)
            if observations:
                data_points = self._build_data_points(observations)
                if data_points:
                    latest = data_points[-1]
                    next_release = self._get_next_release()
                    result = {
                        "data": data_points,
                        "latest": latest,
                        "metadata": {
                            "source": "Australian Bureau of Statistics",
                            "indicator": "Household Spending",
                            "frequency": "monthly",
                            "unit": "%",
                        },
                        "next_release": next_release,
                    }
                    cache_payload = {**result, "last_updated": datetime.now(JST).isoformat()}
                    redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                    self._save_file_cache(cache_payload)
                    return {**result, "cached": False, "source": "abs_api"}

        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
            }

        return {
            "data": [], "latest": None,
            "metadata": {"source": "Australian Bureau of Statistics", "error": "No data available"},
            "next_release": None, "cached": False, "source": "none",
        }

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        try:
            from services.usa.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern("Household Spending", "AU")
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)
            now = datetime.now(JST)
            if (now - last_updated).total_seconds() >= 7 * 24 * 3600:
                return True
            return False
        except Exception as e:
            logger.error(f"Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "AU Household Spending", "source": "ABS",
            "cache_key": self.DATA_CACHE_KEY, "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


au_household_spending_service = AuHouseholdSpendingService()
