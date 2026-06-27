"""
Australian Bureau of Statistics (ABS) 月次CPI サービス

データソース:
- ABS SDMX API
- CPI_M dataflow (Monthly Consumer Price Index indicator)
  - measure=3 (YoY): 2018-09～ (INDEX: 10001, 999901, 999905)
  - measure=1 (Index Numbers): 2017-09～ (INDEX: 999901 SA のみ) → MoM手動計算
- CPI dataflow (Consumer Price Index) — 2024-05～ (MoM+YoY, Weighted Median含む)

3系列:
- All groups CPI, seasonally adjusted (999901) - 総合CPI(季節調整済み)
- Trimmed Mean (CPI_M: 999905, CPI: 999902) - トリム平均
- Weighted Median (CPI only: 999903) - 加重中央値 (2024-05～)

Measures:
- 1 = Index Numbers — CPI_Mで999901のみ取得可、MoM計算用
- 2 = MoM (%) — CPIデータフローのみ
- 3 = YoY (%) — CPI_M + CPI

発表スケジュール: 毎月（四半期CPIは別）
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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "abs_monthly_cpi_cache.json"

# ABS API設定
ABS_API_BASE = "https://data.api.abs.gov.au/rest/data"

# CPI_M: Monthly CPI Indicator
# measure=3 (YoY): INDEX 10001, 999901, 999905 (2018-09～)
# measure=1 (Index Numbers): INDEX 999901 SA only (2017-09～) → MoM手動計算用
CPI_M_DATAFLOW = "ABS,CPI_M,"
CPI_M_YOY_KEY = "3.10001+999901+999905..50.M"
CPI_M_YOY_URL = f"{ABS_API_BASE}/{CPI_M_DATAFLOW}/{CPI_M_YOY_KEY}?dimensionAtObservation=AllDimensions"
CPI_M_INDEX_KEY = "1.999901..50.M"
CPI_M_INDEX_URL = f"{ABS_API_BASE}/{CPI_M_DATAFLOW}/{CPI_M_INDEX_KEY}?dimensionAtObservation=AllDimensions"

# CPI: Consumer Price Index (2024-05～, MoM+YoY, Weighted Median含む)
# INDEX: 999901=AllGroupsSA, 999902=TrimmedMean, 999903=WeightedMedian
CPI_DATAFLOW = "ABS,CPI,"
CPI_KEY = "2+3.999901+999902+999903..50.M"
CPI_URL = f"{ABS_API_BASE}/{CPI_DATAFLOW}/{CPI_KEY}?dimensionAtObservation=AllDimensions"

# FMPイベントパターン
FMP_EVENT_PATTERNS = ["Monthly CPI Indicator", "Inflation Rate MoM"]


class AbsMonthlyCpiService:
    """ABS Monthly CPI Service"""

    DATA_CACHE_KEY = "australia:abs_monthly_cpi:data"

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
        """
        SDMX JSONレスポンスをパースして
        [{measure_code, index_code, time_period, value}, ...] を返す
        """
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

            # Build index -> code mappings for each dimension
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
                        "measure": codes.get("MEASURE", ""),
                        "index": codes.get("INDEX", ""),
                        "time_period": codes.get("TIME_PERIOD", ""),
                        "value": value,
                    }
                )

        except Exception as e:
            logger.error(f"Error parsing SDMX data: {e}")

        return result

    def _compute_mom_from_index(
        self, index_obs: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Index Numbers (measure=1) から前月比を手動計算

        Returns:
            {"2017-10": 0.12, "2017-11": -0.05, ...}  (date_str -> MoM %)
        """
        # time_period -> index value のマップ（999901 SA のみ）
        index_map: Dict[str, float] = {}
        for obs in index_obs:
            if obs["index"] == "999901" and obs["measure"] == "1":
                tp = obs["time_period"]
                if tp:
                    index_map[tp] = obs["value"]

        # 時系列順にソートして前月比計算
        sorted_periods = sorted(index_map.keys())
        mom_map: Dict[str, float] = {}
        for i in range(1, len(sorted_periods)):
            prev_tp = sorted_periods[i - 1]
            curr_tp = sorted_periods[i]
            prev_val = index_map[prev_tp]
            curr_val = index_map[curr_tp]
            if prev_val and prev_val > 0:
                mom = ((curr_val / prev_val) - 1) * 100
                mom_map[curr_tp] = round(mom, 2)

        logger.info(f"Computed {len(mom_map)} MoM values from Index Numbers")
        return mom_map

    def _merge_data(
        self,
        cpi_m_yoy_obs: List[Dict[str, Any]],
        cpi_m_index_obs: List[Dict[str, Any]],
        cpi_obs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        CPI_M (YoY長期 + Index Numbers) と CPI (MoM+YoY最新) のデータをマージ

        CPI_M provides:
        - 10001 (measure=3): All groups CPI YoY (原系列)
        - 999901 (measure=3): All groups CPI SA YoY
        - 999905 (measure=3): Trimmed Mean YoY
        - 999901 (measure=1): All groups CPI SA Index Numbers → MoM計算

        CPI provides:
        - 999901 (measure=2/3): All groups CPI SA MoM/YoY
        - 999902 (measure=2/3): Trimmed Mean MoM/YoY
        - 999903 (measure=2/3): Weighted Median MoM/YoY
        """
        parsed_points: Dict[str, Dict[str, Any]] = {}

        def ensure_point(date_str: str) -> Dict[str, Any]:
            if date_str not in parsed_points:
                parsed_points[date_str] = {
                    "date": date_str,
                    "cpi_yoy": None,
                    "cpi_mom": None,
                    "trimmed_mean_yoy": None,
                    "trimmed_mean_mom": None,
                    "weighted_median_yoy": None,
                    "weighted_median_mom": None,
                }
            return parsed_points[date_str]

        # Phase 1: CPI_M YoY data (long history)
        for obs in cpi_m_yoy_obs:
            tp = obs["time_period"]
            if not tp:
                continue
            date_str = f"{tp}-01"
            point = ensure_point(date_str)
            val = round(obs["value"], 2)

            if obs["index"] == "999901" and obs["measure"] == "3":
                # All groups CPI SA — YoY
                point["cpi_yoy"] = val
            elif obs["index"] == "10001" and obs["measure"] == "3":
                # All groups CPI (original) — use as fallback if SA not available
                if point["cpi_yoy"] is None:
                    point["cpi_yoy"] = val
            elif obs["index"] == "999905" and obs["measure"] == "3":
                # Trimmed Mean — YoY
                point["trimmed_mean_yoy"] = val

        # Phase 2: CPI_M Index Numbers → MoM手動計算 (総合CPI SA のみ)
        cpi_mom_map = self._compute_mom_from_index(cpi_m_index_obs)
        for tp, mom_val in cpi_mom_map.items():
            date_str = f"{tp}-01"
            point = ensure_point(date_str)
            point["cpi_mom"] = mom_val

        # Phase 3: CPI data (recent, MoM+YoY, includes Weighted Median)
        # CPI dataflow values override CPI_M where both exist
        for obs in cpi_obs:
            tp = obs["time_period"]
            if not tp:
                continue
            date_str = f"{tp}-01"
            point = ensure_point(date_str)
            val = round(obs["value"], 2)

            if obs["index"] == "999901":
                if obs["measure"] == "3":
                    point["cpi_yoy"] = val
                elif obs["measure"] == "2":
                    point["cpi_mom"] = val
            elif obs["index"] == "999902":
                if obs["measure"] == "3":
                    point["trimmed_mean_yoy"] = val
                elif obs["measure"] == "2":
                    point["trimmed_mean_mom"] = val
            elif obs["index"] == "999903":
                if obs["measure"] == "3":
                    point["weighted_median_yoy"] = val
                elif obs["measure"] == "2":
                    point["weighted_median_mom"] = val

        # Sort by date
        result = sorted(parsed_points.values(), key=lambda x: x["date"])
        logger.info(f"Merged {len(result)} CPI data points")
        return result

    def get_monthly_cpi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """月次CPIデータを取得（キャッシュ付き）"""
        # Redisキャッシュ
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

        # ABS APIからデータ取得（3段階フェッチ）
        cpi_m_yoy_obs = []
        cpi_m_index_obs = []
        cpi_obs = []

        # 1. CPI_M YoY (Monthly CPI Indicator) — YoY長期データ (2018-09～)
        raw_cpi_m_yoy = self._fetch_sdmx(CPI_M_YOY_URL)
        if raw_cpi_m_yoy:
            cpi_m_yoy_obs = self._parse_sdmx_observations(raw_cpi_m_yoy)
            logger.info(f"CPI_M YoY: {len(cpi_m_yoy_obs)} observations")

        # 2. CPI_M Index Numbers (999901 SA) — MoM手動計算用 (2017-09～)
        raw_cpi_m_index = self._fetch_sdmx(CPI_M_INDEX_URL)
        if raw_cpi_m_index:
            cpi_m_index_obs = self._parse_sdmx_observations(raw_cpi_m_index)
            logger.info(f"CPI_M Index: {len(cpi_m_index_obs)} observations")

        # 3. CPI (Consumer Price Index) — MoM + 最新YoY + Weighted Median (2024-05～)
        raw_cpi = self._fetch_sdmx(CPI_URL)
        if raw_cpi:
            cpi_obs = self._parse_sdmx_observations(raw_cpi)
            logger.info(f"CPI: {len(cpi_obs)} observations")

        if cpi_m_yoy_obs or cpi_m_index_obs or cpi_obs:
            data_points = self._merge_data(cpi_m_yoy_obs, cpi_m_index_obs, cpi_obs)

            if data_points:
                latest = data_points[-1] if data_points else None
                next_release = self._get_next_release()

                result = {
                    "data": data_points,
                    "latest": latest,
                    "metadata": {
                        "source": "Australian Bureau of Statistics",
                        "indicator": "Monthly Consumer Price Index",
                        "frequency": "monthly",
                        "unit": "%",
                    },
                    "next_release": next_release,
                }

                # 発表時刻レース対策（ラグガード）: 取得データが新月へ進んでいない場合は
                # last_updated を発表直前に据え置き、ABS SDMX反映後の再取得を促す。
                # （発表 11:30 AEST ちょうどの再構築がABS APIの新月反映を先行すると、
                #  now刻みで should_refresh が「消化済み」と誤判定して凍結するため）
                from services.australia.fmp_next_release_utils import resolve_last_updated_after_fetch
                _prev_cache = redis_client.get(self.DATA_CACHE_KEY)
                _prev_latest = _prev_cache.get("latest") if isinstance(_prev_cache, dict) else None
                _resolved_last_updated = resolve_last_updated_after_fetch(
                    FMP_EVENT_PATTERNS,
                    latest.get("date") if isinstance(latest, dict) else None,
                    _prev_latest.get("date") if isinstance(_prev_latest, dict) else None,
                    _prev_cache.get("last_updated") if isinstance(_prev_cache, dict) else None,
                    country="AU",
                )

                # キャッシュ保存
                cache_payload = {
                    **result,
                    "last_updated": _resolved_last_updated,
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
            from services.australia.fmp_next_release_utils import get_next_release_by_pattern

            return get_next_release_by_pattern(FMP_EVENT_PATTERNS[0], "AU")
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

            # 発表認識型: FMP発表(=ABS公式発表)が last_updated より後にあれば更新。
            # ラグガードで last_updated を発表直前に据え置いた場合も、ここで再取得を促す。
            try:
                from services.australia.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country="AU"):
                        return True
            except Exception as e:
                logger.warning(f"Error checking FMP refresh: {e}")

            # 7日以上経過
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
            "indicator": "AU Monthly CPI",
            "source": "ABS",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
abs_monthly_cpi_service = AbsMonthlyCpiService()
