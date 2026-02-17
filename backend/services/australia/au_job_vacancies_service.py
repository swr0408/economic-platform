"""
Australian Bureau of Statistics (ABS) 求人件数（Job Vacancies）サービス

データソース:
- ABS SDMX API (Job Vacancies)
- JV dataflow: MEASURE M1 = Job Vacancies (thousands)
- Sector: Private and Public (7), Industry: All (TOT)
- TSEST: Seasonally Adjusted (20), Region: Australia (AUS)
- Frequency: Quarterly (Q)

発表スケジュール: 四半期
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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_job_vacancies_cache.json"

# ABS API設定
ABS_API_BASE = "https://data.api.abs.gov.au/rest/data"
JV_DATAFLOW = "ABS,JV,1.0"
JV_KEY = "M1.7.TOT.20.AUS.Q"
JV_URL = f"{ABS_API_BASE}/{JV_DATAFLOW}/{JV_KEY}?startPeriod=1979-Q2&dimensionAtObservation=AllDimensions"

QUARTER_MONTH_MAP = {"Q1": "03", "Q2": "06", "Q3": "09", "Q4": "12"}


class AuJobVacanciesService:
    """ABS Job Vacancies Service"""

    DATA_CACHE_KEY = "australia:au_job_vacancies:data"

    def __init__(self):
        pass

    def _fetch_sdmx(self, url: str) -> Optional[Dict[str, Any]]:
        """ABS SDMX APIからデータを取得"""
        try:
            logger.info(f"Fetching ABS data from {url}")
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
            logger.error(f"Error fetching ABS data: {e}")
            return None

    def _quarter_to_date(self, quarter_str: str) -> str:
        """'2025-Q4' -> '2025-12-01'"""
        parts = quarter_str.split("-")
        if len(parts) == 2:
            year = parts[0]
            q = parts[1]
            month = QUARTER_MONTH_MAP.get(q, "12")
            return f"{year}-{month}-01"
        return quarter_str

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
                    "time_period": codes.get("TIME_PERIOD", ""),
                    "value": value,
                })
        except Exception as e:
            logger.error(f"Error parsing SDMX data: {e}")
        return result

    def _build_data_points(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """観測データからデータポイントを構築"""
        data_points = []
        for obs in observations:
            tp = obs.get("time_period", "")
            if not tp:
                continue
            data_points.append({
                "date": self._quarter_to_date(tp),
                "value": round(obs["value"], 1),
            })
        data_points.sort(key=lambda x: x["date"])
        logger.info(f"Built {len(data_points)} Job Vacancies data points")
        return data_points

    def get_au_job_vacancies_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """求人件数データを取得（キャッシュ付き）"""
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

        raw_data = self._fetch_sdmx(JV_URL)
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
                            "indicator": "Job Vacancies",
                            "frequency": "quarterly",
                            "unit": "thousands",
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
            return get_next_release_by_pattern("Job Vacancies", "AU")
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
            "indicator": "AU Job Vacancies", "source": "ABS",
            "cache_key": self.DATA_CACHE_KEY, "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


au_job_vacancies_service = AuJobVacanciesService()
