"""
オーストラリア アンダー・ユーティライゼーション（不足雇用含む）サービス

データソース: ABS SDMX API（LF_UNDER dataflow）
- 月次・季節調整済（TSEST=20）、Persons（SEX=3）、Total age（AGE=1599）、Australia（REGION=AUS）
- M24 = Underutilisation rate
- M23 = Underemployment rate (proportion of labour force)
- M13 = Unemployment rate

【移行ノート】旧実装は ABS Excel「Table 23」(6202023.xlsx) を latest-release から
スクレイプしていたが、ABS がテーブルを X28/X29 にリネームし旧URLが HTTP 404 となり
取得不能になった（March で固着）。脆い Excel URL/レイアウト依存を排し、他のAU雇用
指標（失業率/参加率等）と同じ SDMX API 方式に統一。LF_UNDER は同一系列を提供し、
テーブル再番号付けの影響を受けない。

発表スケジュール: 毎月（Labour Force Survey）
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
DATA_CACHE_FILE = CACHE_DIR / "au_underutilization_cache.json"

# ABS SDMX API（LF_UNDER dataflow）
ABS_API_BASE = "https://data.api.abs.gov.au/rest/data"
LF_UNDER_DATAFLOW = "ABS,LF_UNDER"
# 次元順: PARM_ITEM.SEX.AGE.TSEST.REGION.FREQ
# M24=Underutilisation / M23=Underemployment / M13=Unemployment rate
# SEX=3 Persons, AGE=1599 Total, TSEST=20 Seasonally Adjusted, REGION=AUS, FREQ=M
LF_UNDER_KEY = "M24+M23+M13.3.1599.20.AUS.M"
LF_UNDER_URL = (
    f"{ABS_API_BASE}/{LF_UNDER_DATAFLOW}/{LF_UNDER_KEY}"
    f"?startPeriod=2000-01&dimensionAtObservation=AllDimensions"
)

# PARM_ITEM コード → 出力フィールド名
PARM_TO_FIELD = {
    "M24": "underutilisation",
    "M23": "underemployment",
    "M13": "unemployment",
}

# FMPイベントパターン（失業率と同じ発表日）
FMP_EVENT_PATTERN = "Unemployment Rate"
FMP_COUNTRY = "AU"


class AuUnderutilizationService:
    """オーストラリア アンダー・ユーティライゼーション サービス"""

    DATA_CACHE_KEY = "australia:au_underutilization:data"

    def __init__(self):
        pass

    def _fetch_sdmx(self, url: str) -> Optional[Dict[str, Any]]:
        """ABS SDMX APIからデータを取得"""
        try:
            logger.info(f"Fetching ABS LF_UNDER data from {url}")
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
            logger.error(f"Error fetching ABS LF_UNDER data: {e}")
            return None

    def _parse_sdmx(self, raw_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """SDMX JSONを {field: [{"date","value"}, ...]} 形式に変換"""
        result: Dict[str, List[Dict[str, Any]]] = {f: [] for f in PARM_TO_FIELD.values()}
        try:
            data = raw_data.get("data", {})
            datasets = data.get("dataSets", [])
            structures = data.get("structures", [])
            if not datasets or not structures:
                return result

            dimensions = structures[0].get("dimensions", {}).get("observation", [])
            dim_ids = [d.get("id", "") for d in dimensions]
            lookups = {
                d.get("id", ""): {str(i): v.get("id", "") for i, v in enumerate(d.get("values", []))}
                for d in dimensions
            }
            if "PARM_ITEM" not in dim_ids or "TIME_PERIOD" not in dim_ids:
                logger.warning("[AuUnderutil] PARM_ITEM/TIME_PERIOD dimension not found")
                return result
            pi = dim_ids.index("PARM_ITEM")
            ti = dim_ids.index("TIME_PERIOD")

            observations = datasets[0].get("observations", {})
            for obs_key, obs_value in observations.items():
                if not obs_value or obs_value[0] is None:
                    continue
                idxs = obs_key.split(":")
                parm = lookups.get("PARM_ITEM", {}).get(idxs[pi])
                field = PARM_TO_FIELD.get(parm)
                if not field:
                    continue
                tp = lookups.get("TIME_PERIOD", {}).get(idxs[ti])
                if not tp:
                    continue
                result[field].append({
                    "date": f"{tp}-01",
                    "value": round(float(obs_value[0]), 2),
                })

            for field in result:
                result[field].sort(key=lambda x: x["date"])
                logger.info(f"[AuUnderutil] Parsed {len(result[field])} {field} observations")
        except Exception as e:
            logger.error(f"Error parsing ABS LF_UNDER SDMX: {e}")
        return result

    def _build_data_points(self, parsed: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """3系列のデータを日付でマージ"""
        underutil_map = {obs["date"]: obs["value"] for obs in parsed.get("underutilisation", [])}
        underempl_map = {obs["date"]: obs["value"] for obs in parsed.get("underemployment", [])}
        unempl_map = {obs["date"]: obs["value"] for obs in parsed.get("unemployment", [])}

        # 全日付を統合
        all_dates = sorted(set(
            list(underutil_map.keys()) +
            list(underempl_map.keys()) +
            list(unempl_map.keys())
        ))

        data_points = []
        for date_str in all_dates:
            underutil = underutil_map.get(date_str)
            underempl = underempl_map.get(date_str)
            unempl = unempl_map.get(date_str)

            # メイン系列（underutilisation）がある場合のみ追加
            if underutil is not None:
                data_points.append({
                    "date": date_str,
                    "underutilisation": underutil,
                    "underemployment": underempl,
                    "unemployment": unempl,
                })

        logger.info(f"Built {len(data_points)} underutilization data points")
        return data_points

    def get_au_underutilization_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """アンダー・ユーティライゼーションデータを取得（キャッシュ付き）"""
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

        raw_data = self._fetch_sdmx(LF_UNDER_URL)
        if raw_data:
            parsed = self._parse_sdmx(raw_data)
            if parsed.get("underutilisation"):
                data_points = self._build_data_points(parsed)
                if data_points:
                    latest = data_points[-1]

                    # API遅延ガード: force_refresh時に最新日付が進んでいなければ
                    # キャッシュを書き換えない（次のスケジューラ波でリトライ）
                    if force_refresh and existing_cached_data:
                        existing_date = (existing_cached_data.get("latest") or {}).get("date")
                        new_date = latest.get("date") if latest else None
                        if existing_date and new_date and new_date <= existing_date:
                            logger.warning(
                                f"[AuUnderutil] force_refresh requested but API returned "
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
                            "source": "Australian Bureau of Statistics (LF_UNDER)",
                            "indicator": "Underutilisation Rate (Labour Force, Seasonally Adjusted)",
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
            from services.australia.fmp_next_release_utils import get_next_release_by_pattern
            result = get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
            return result
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        try:
            from services.australia.fmp_next_release_utils import should_refresh_by_pattern
            return should_refresh_by_pattern(
                FMP_EVENT_PATTERN,
                last_updated_str,
                country=FMP_COUNTRY,
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
            "indicator": "AU Underutilization Rate",
            "source": "ABS SDMX (LF_UNDER)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
au_underutilization_service = AuUnderutilizationService()
