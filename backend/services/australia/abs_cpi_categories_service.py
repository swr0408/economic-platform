"""
Australian Bureau of Statistics (ABS) CPI カテゴリ別サービス

データソース:
- ABS SDMX API — CPI_M dataflow
  - measure=3 (YoY): 2018-09～ (原系列 TSEST=10)
  - measure=1 (Index Numbers): 2017-09～ (原系列 TSEST=10) → MoM手動計算

6系列:
- Goods (104101) - 財
- Services (104104) - サービス
- Electricity (40055) - 電力
- Rents (115522) - 家賃
- New dwellings (131186) - 新築住宅
- Food & non-alcoholic beverages (20001) - 食品・非アルコール飲料

発表スケジュール: 月次CPIと同タイミング
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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "abs_cpi_categories_cache.json"

# ABS API設定
ABS_API_BASE = "https://data.api.abs.gov.au/rest/data"
# 2025-11: ABS は旧「Monthly CPI indicator」(dataflow CPI_M, 2025-09 で終了) を廃止し、
# 完全版 monthly CPI を dataflow CPI v2.0.0 (FREQ=M) に統合した。
# 次元順は同一 (MEASURE.INDEX.TSEST.REGION.FREQ)、REGION=50 は「Australia」に改称。
# 既存のカテゴリ INDEX コードはそのまま利用可。バージョンを固定し、ABS が次版へ
# 移行した場合は staleness monitor が検知する。
CPI_M_DATAFLOW = "ABS,CPI,2.0.0"

# カテゴリINDEXコード
CATEGORY_INDICES = "104101+104104+40055+115522+131186+20001"

# YoY (measure=3, 原系列 TSEST=10)
CPI_M_CAT_YOY_KEY = f"3.{CATEGORY_INDICES}.10.50.M"
CPI_M_CAT_YOY_URL = f"{ABS_API_BASE}/{CPI_M_DATAFLOW}/{CPI_M_CAT_YOY_KEY}?dimensionAtObservation=AllDimensions"

# Index Numbers (measure=1, 原系列 TSEST=10) → MoM手動計算用
CPI_M_CAT_INDEX_KEY = f"1.{CATEGORY_INDICES}.10.50.M"
CPI_M_CAT_INDEX_URL = f"{ABS_API_BASE}/{CPI_M_DATAFLOW}/{CPI_M_CAT_INDEX_KEY}?dimensionAtObservation=AllDimensions"

# 旧 CPI_M dataflow（2025-09 で更新停止）。完全な履歴 2018-09〜2025-09 を持つため
# 履歴ソースとして併用する。v2.0.0 は一部カテゴリ（goods/services/food 等）の履歴が
# 2025-04〜と短いため、旧dataflowでマージ補完する。
# 注意: index の base は両dataflowで異なる（v2.0.0 は 2025-09=100 へリベース、旧は別base）。
# YoYは base 非依存なので連結可（重複は新優先）。MoM は dataflow ごとに算出してから
# マージし、base が違う境界（2025-09→2025-10）を跨いだ計算を避ける。
CPI_M_LEGACY_DATAFLOW = "ABS,CPI_M,"
CPI_M_LEGACY_CAT_YOY_URL = f"{ABS_API_BASE}/{CPI_M_LEGACY_DATAFLOW}/{CPI_M_CAT_YOY_KEY}?dimensionAtObservation=AllDimensions"
CPI_M_LEGACY_CAT_INDEX_URL = f"{ABS_API_BASE}/{CPI_M_LEGACY_DATAFLOW}/{CPI_M_CAT_INDEX_KEY}?dimensionAtObservation=AllDimensions"

# INDEX code → フィールド名マッピング
INDEX_TO_FIELD = {
    "104101": "goods",
    "104104": "services",
    "40055": "electricity",
    "115522": "rents",
    "131186": "new_dwellings",
    "20001": "food",
}

# FMPイベントパターン（月次CPIと同じ）
# "Inflation Rate MoM" がFMPのAU CPI発表イベント実名に一致（発表時刻照合用）。
FMP_EVENT_PATTERNS = ["Monthly CPI Indicator", "Inflation Rate MoM"]


class AbsCpiCategoriesService:
    """ABS CPI Categories Service"""

    DATA_CACHE_KEY = "australia:abs_cpi_categories:data"

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
        """SDMX JSONレスポンスをパースして観測値リストを返す"""
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
    ) -> Dict[str, Dict[str, float]]:
        """
        Index Numbers から各カテゴリの前月比を手動計算

        Returns:
            {"goods": {"2017-10": 0.12, ...}, "services": {"2017-10": ...}, ...}
        """
        # カテゴリ別の time_period -> index value マップ
        index_maps: Dict[str, Dict[str, float]] = {
            field: {} for field in INDEX_TO_FIELD.values()
        }

        for obs in index_obs:
            if obs["measure"] != "1":
                continue
            field = INDEX_TO_FIELD.get(obs["index"])
            if field and obs["time_period"]:
                index_maps[field][obs["time_period"]] = obs["value"]

        # 各カテゴリの前月比計算
        mom_maps: Dict[str, Dict[str, float]] = {}
        for field, idx_map in index_maps.items():
            sorted_periods = sorted(idx_map.keys())
            mom_map: Dict[str, float] = {}
            for i in range(1, len(sorted_periods)):
                prev_val = idx_map[sorted_periods[i - 1]]
                curr_val = idx_map[sorted_periods[i]]
                if prev_val and prev_val > 0:
                    mom = ((curr_val / prev_val) - 1) * 100
                    mom_map[sorted_periods[i]] = round(mom, 2)
            mom_maps[field] = mom_map

        return mom_maps

    def _merge_data(
        self,
        yoy_obs: List[Dict[str, Any]],
        mom_maps: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        """YoY観測値と（事前算出済みの）MoMマップをマージして時系列を構築。

        yoy_obs は新旧dataflowを連結したリスト（後勝ち＝新dataflowが重複月を上書き）。
        mom_maps は dataflow ごとに算出してマージ済み（base差の境界跨ぎを避けるため）。
        """
        parsed_points: Dict[str, Dict[str, Any]] = {}

        fields = list(INDEX_TO_FIELD.values())

        def ensure_point(date_str: str) -> Dict[str, Any]:
            if date_str not in parsed_points:
                point: Dict[str, Any] = {"date": date_str}
                for f in fields:
                    point[f"{f}_yoy"] = None
                    point[f"{f}_mom"] = None
                parsed_points[date_str] = point
            return parsed_points[date_str]

        # Phase 1: YoY data（後勝ちで新dataflow優先）
        for obs in yoy_obs:
            if obs["measure"] != "3":
                continue
            field = INDEX_TO_FIELD.get(obs["index"])
            if not field or not obs["time_period"]:
                continue
            date_str = f"{obs['time_period']}-01"
            point = ensure_point(date_str)
            point[f"{field}_yoy"] = round(obs["value"], 2)

        # Phase 2: MoM（事前算出済みマップ）
        for field, mom_map in mom_maps.items():
            for tp, mom_val in mom_map.items():
                date_str = f"{tp}-01"
                point = ensure_point(date_str)
                point[f"{field}_mom"] = mom_val

        result = sorted(parsed_points.values(), key=lambda x: x["date"])
        logger.info(f"Merged {len(result)} CPI categories data points")
        return result

    def get_cpi_categories_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """CPIカテゴリ別データを取得（キャッシュ付き）"""
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

        # ABS APIからデータ取得（新旧2 dataflow をマージ）
        # 旧 CPI_M = 履歴(2018-09〜2025-09)、新 CPI v2.0.0 = 直近。一部カテゴリの
        # 履歴が新dataflowで短い問題を、旧dataflowで補完する。
        def _fetch(url: str) -> List[Dict[str, Any]]:
            raw = self._fetch_sdmx(url)
            return self._parse_sdmx_observations(raw) if raw else []

        legacy_yoy = _fetch(CPI_M_LEGACY_CAT_YOY_URL)
        legacy_index = _fetch(CPI_M_LEGACY_CAT_INDEX_URL)
        new_yoy = _fetch(CPI_M_CAT_YOY_URL)
        new_index = _fetch(CPI_M_CAT_INDEX_URL)
        logger.info(
            f"CPI Categories obs — legacy(yoy={len(legacy_yoy)},index={len(legacy_index)}) "
            f"new(yoy={len(new_yoy)},index={len(new_index)})"
        )

        # YoY: 旧→新 の順に連結（_merge_data Phase1 の後勝ちで重複月は新が優先）
        yoy_obs = legacy_yoy + new_yoy

        # MoM: index の base が両dataflowで異なるため、dataflow ごとに MoM を算出してから
        # マージ（新優先）。これで base 差の境界(2025-09→2025-10)を跨いだ誤計算を避ける。
        mom_legacy = self._compute_mom_from_index(legacy_index)
        mom_new = self._compute_mom_from_index(new_index)
        mom_maps: Dict[str, Dict[str, float]] = {
            field: {**mom_legacy.get(field, {}), **mom_new.get(field, {})}
            for field in INDEX_TO_FIELD.values()
        }

        if yoy_obs or any(mom_maps.values()):
            data_points = self._merge_data(yoy_obs, mom_maps)

            if data_points:
                latest = data_points[-1] if data_points else None
                next_release = self._get_next_release()

                result = {
                    "data": data_points,
                    "latest": latest,
                    "metadata": {
                        "source": "Australian Bureau of Statistics",
                        "indicator": "Monthly CPI Categories",
                        "frequency": "monthly",
                        "unit": "%",
                    },
                    "next_release": next_release,
                }

                # 発表時刻レース対策（ラグガード）: 取得データが新月へ進んでいない場合は
                # last_updated を発表直前に据え置き、ABS SDMX反映後の再取得を促す。
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
            # ラグガードで last_updated を発表直前に据え置いた場合も再取得を促す。
            try:
                from services.australia.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country="AU"):
                        return True
            except Exception as e:
                logger.warning(f"Error checking FMP refresh: {e}")

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
            "indicator": "AU CPI Categories",
            "source": "ABS",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
abs_cpi_categories_service = AbsCpiCategoriesService()
