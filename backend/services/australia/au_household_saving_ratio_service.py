"""
オーストラリア 家計貯蓄率（Household Saving Ratio）サービス

データソース:
- ABS SDMX API (ANA_AGG dataflow)
- M7.HSR = Household saving ratio
- TSEST=20 (Seasonally Adjusted), FREQ=Q (Quarterly)
- 生値（%）をそのまま使用し、QoQ変化幅（pt）とYoY変化幅（pt）を算出

発表スケジュール: 四半期（National Accounts と同日）
"""
import json
import logging
import re
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
DATA_CACHE_FILE = CACHE_DIR / "au_household_saving_ratio_cache.json"

# ABS API設定
ABS_API_BASE = "https://data.api.abs.gov.au/rest/data"
DATAFLOW = "ABS,ANA_AGG,1.0.0"
DATA_KEY = "M7.HSR.20..Q"
DATA_URL = f"{ABS_API_BASE}/{DATAFLOW}/{DATA_KEY}?startPeriod=1959-Q3&dimensionAtObservation=AllDimensions"


class AuHouseholdSavingRatioService:
    """オーストラリア家計貯蓄率サービス"""

    DATA_CACHE_KEY = "australia:au_household_saving_ratio:data"
    FMP_EVENT_PATTERN = "GDP Growth Rate QoQ"
    FMP_COUNTRY = "AU"

    def __init__(self):
        pass

    def _fetch_sdmx(self, url: str) -> Optional[Dict[str, Any]]:
        """ABS SDMX APIからデータを取得"""
        try:
            logger.info(f"Fetching ABS ANA_AGG data from {url}")
            response = requests.get(
                url,
                headers={
                    "Accept": "application/vnd.sdmx.data+json",
                    "User-Agent": "Mozilla/5.0 (economic-platform)",
                },
                timeout=30,
            )
            if response.status_code != 200:
                logger.error(f"ABS API returned HTTP {response.status_code}")
                return None
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching ABS ANA_AGG data: {e}")
            return None

    def _parse_sdmx_observations(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """SDMX JSONレスポンスをパースして時系列データを抽出"""
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

            # TIME_PERIODディメンションのルックアップを構築
            tp_dim_idx = None
            tp_lookup = {}
            for i, dim in enumerate(dimensions):
                if dim.get("id") == "TIME_PERIOD":
                    tp_dim_idx = i
                    tp_lookup = {str(j): v.get("id", "") for j, v in enumerate(dim.get("values", []))}
                    break

            if tp_dim_idx is None:
                return []

            for obs_key, obs_value in observations.items():
                if obs_value is None or obs_value[0] is None:
                    continue
                value = obs_value[0]
                indices = obs_key.split(":")
                tp_idx = indices[tp_dim_idx] if tp_dim_idx < len(indices) else None
                if tp_idx is None:
                    continue
                time_period = tp_lookup.get(tp_idx, "")
                if time_period:
                    result.append({
                        "time_period": time_period,
                        "value": value,
                    })

        except Exception as e:
            logger.error(f"Error parsing SDMX ANA_AGG data: {e}")
        return result

    def _build_data_points(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生値（%）からQoQ変化幅（pt）とYoY変化幅（pt）を算出"""
        # 日付順にソート
        observations.sort(key=lambda x: x["time_period"])

        data_points = []
        for i, obs in enumerate(observations):
            tp = obs["time_period"]
            val = obs["value"]
            qoq = None
            yoy = None

            # QoQ: 前四半期との差分（ポイント）
            if i >= 1:
                prev = observations[i - 1]["value"]
                if prev is not None:
                    qoq = round(val - prev, 2)

            # YoY: 前年同期との差分（ポイント、4四半期前）
            if i >= 4:
                prev4 = observations[i - 4]["value"]
                if prev4 is not None:
                    yoy = round(val - prev4, 2)

            data_points.append({
                "date": tp,
                "value": round(val, 1),
                "qoq": qoq,
                "yoy": yoy,
            })

        logger.info(f"Built {len(data_points)} Household Saving Ratio data points")
        return data_points

    def get_au_household_saving_ratio_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """家計貯蓄率データを取得（キャッシュ付き）"""
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

        raw_data = self._fetch_sdmx(DATA_URL)
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
                            "indicator": "Household Saving Ratio",
                            "frequency": "quarterly",
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
            from services.australia.fmp_next_release_utils import get_next_release_by_pattern
            result = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)
            if result:
                label = result.get("label", "")
                q_match = re.search(r"\(Q[1-4]\)", label)
                quarter = q_match.group(0) if q_match else ""
                result["label"] = f"家計貯蓄率 {quarter}".strip()
            return result
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        try:
            from services.australia.fmp_next_release_utils import should_refresh_by_pattern
            return should_refresh_by_pattern(
                self.FMP_EVENT_PATTERN,
                last_updated_str,
                country=self.FMP_COUNTRY,
            )
        except Exception as e:
            logger.error(f"Error in should_refresh: {e}")
            return False

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
            "indicator": "AU Household Saving Ratio", "source": "ABS (ANA_AGG)",
            "cache_key": self.DATA_CACHE_KEY, "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


au_household_saving_ratio_service = AuHouseholdSavingRatioService()
