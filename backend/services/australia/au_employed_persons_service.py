"""
Australian Bureau of Statistics (ABS) 雇用者数サービス

データソース:
- ABS SDMX API (Labour Force Survey)
- LF dataflow: M3 = Employed persons (thousands)
- Sex: Persons (3), Age: Total (1599), TSEST: Seasonally Adjusted (20)
- Region: Australia (AUS), Frequency: Monthly (M)

算出系列:
- value: 雇用者数（千人）
- mom_change: 前月増減（千人）
- yoy_change: 前年比（%）

発表スケジュール: 毎月（通常第3木曜日）
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
AEST = ZoneInfo("Australia/Sydney")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_employed_persons_cache.json"

# ABS API設定
ABS_API_BASE = "https://data.api.abs.gov.au/rest/data"

# LF: Labour Force Survey
# M3 = Employed persons (thousands)
LF_DATAFLOW = "ABS,LF,1.0.0"
LF_KEY = "M3.3.1599.20.AUS.M"
LF_URL = f"{ABS_API_BASE}/{LF_DATAFLOW}/{LF_KEY}?startPeriod=2000-01&dimensionAtObservation=AllDimensions"

# FMPイベントパターン
FMP_EVENT_PATTERN = "Employment Change"


class AuEmployedPersonsService:
    """ABS Employed Persons Service"""

    DATA_CACHE_KEY = "australia:au_employed_persons:data"

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

    def _parse_sdmx_observations(
        self, raw_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """SDMX JSONレスポンスをパースして [{time_period, value}, ...] を返す"""
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
                dim_lookups[dim_id] = {
                    str(i): v.get("id", "") for i, v in enumerate(values)
                }

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

                result.append(
                    {
                        "time_period": codes.get("TIME_PERIOD", ""),
                        "value": value,
                    }
                )

        except Exception as e:
            logger.error(f"Error parsing SDMX data: {e}")

        return result

    def _build_data_points(
        self, observations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        観測データからデータポイントを構築

        value: 雇用者数（千人）
        mom_change: 前月増減（千人）
        yoy_change: 前年比（%）
        """
        # time_period -> value マップ
        raw_map: Dict[str, float] = {}
        for obs in observations:
            tp = obs.get("time_period", "")
            if tp:
                raw_map[tp] = obs["value"]

        sorted_periods = sorted(raw_map.keys())

        data_points = []
        for tp in sorted_periods:
            date_str = f"{tp}-01"
            value = round(raw_map[tp], 2)

            # 前月増減（千人）
            mom_change = None
            year, month = tp.split("-")
            prev_month = int(month) - 1
            prev_year = int(year)
            if prev_month == 0:
                prev_month = 12
                prev_year -= 1
            prev_tp = f"{prev_year:04d}-{prev_month:02d}"
            if prev_tp in raw_map:
                mom_change = round(raw_map[tp] - raw_map[prev_tp], 2)

            # 前年比（%）
            yoy_change = None
            prev_year_tp = f"{int(year) - 1:04d}-{month}"
            if prev_year_tp in raw_map and raw_map[prev_year_tp] > 0:
                yoy_change = round(
                    ((raw_map[tp] - raw_map[prev_year_tp]) / raw_map[prev_year_tp]) * 100, 2
                )

            data_points.append({
                "date": date_str,
                "value": value,
                "mom_change": mom_change,
                "yoy_change": yoy_change,
            })

        logger.info(f"Built {len(data_points)} employed persons data points")
        return data_points

    def get_au_employed_persons_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """雇用者数データを取得（キャッシュ付き）"""
        # Redisキャッシュ
        existing_cached_data = redis_client.get(self.DATA_CACHE_KEY)

        if not force_refresh:
            if existing_cached_data:
                last_updated_str = existing_cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": existing_cached_data.get("data", []),
                        "latest": existing_cached_data.get("latest"),
                        "metadata": existing_cached_data.get("metadata", {}),
                        "next_release": existing_cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                    }

        # ABS APIからデータ取得
        raw_data = self._fetch_sdmx(LF_URL)
        if raw_data:
            observations = self._parse_sdmx_observations(raw_data)
            if observations:
                data_points = self._build_data_points(observations)

                if data_points:
                    latest = data_points[-1] if data_points else None

                    # API遅延ガード: force_refresh時に最新日付が進んでいなければ
                    # キャッシュを書き換えない（次のスケジューラ波でリトライ）
                    if force_refresh and existing_cached_data:
                        existing_latest = existing_cached_data.get("latest") or {}
                        existing_date = existing_latest.get("date")
                        new_date = latest.get("date") if latest else None
                        if existing_date and new_date and new_date <= existing_date:
                            logger.warning(
                                f"[AuEmployedPersons] force_refresh requested but API returned "
                                f"same/older period ({new_date} <= cached {existing_date}). "
                                f"Skipping cache write to allow retry on next scheduler tick."
                            )
                            return {
                                "data": existing_cached_data.get("data", []),
                                "latest": existing_cached_data.get("latest"),
                                "metadata": existing_cached_data.get("metadata", {}),
                                "next_release": existing_cached_data.get("next_release"),
                                "cached": True,
                                "source": "redis (api lag detected)",
                            }

                    next_release = self._get_next_release()

                    result = {
                        "data": data_points,
                        "latest": latest,
                        "metadata": {
                            "source": "Australian Bureau of Statistics",
                            "indicator": "Employed Persons",
                            "frequency": "monthly",
                            "unit": "thousands",
                        },
                        "next_release": next_release,
                    }

                    # キャッシュ保存
                    cache_payload = {
                        **result,
                        "last_updated": datetime.now(JST).isoformat(),
                    }
                    redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                    self._save_file_cache(cache_payload)

                    return {
                        **result,
                        "cached": False,
                        "source": "abs_api",
                    }

        # ファイルキャッシュフォールバック
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
            "data": [],
            "latest": None,
            "metadata": {
                "source": "Australian Bureau of Statistics",
                "error": "No data available",
            },
            "next_release": None,
            "cached": False,
            "source": "none",
        }

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        """FMPから次回発表日を取得"""
        try:
            from services.usa.fmp_next_release_utils import get_next_release_by_pattern

            return get_next_release_by_pattern(FMP_EVENT_PATTERN, "AU")
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定"""
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
            "indicator": "AU Employed Persons",
            "source": "ABS",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
au_employed_persons_service = AuEmployedPersonsService()
