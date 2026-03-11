"""
米国ガソリン在庫 / 製油稼働率 サービス

データソース:
  - EIA: 週次Excelファイル (XLS)
  - ガソリン在庫: https://www.eia.gov/dnav/pet/xls/PET_STOC_WSTK_DCU_NUS_W.xls
    - WGTSTUS1: Total Gasoline (Thousand Barrels)
  - 製油稼働率: https://www.eia.gov/dnav/pet/xls/PET_PNP_WIUP_DCU_NUS_W.xls
    - WPULEUS3: Percent Utilization of Refinery Operable Capacity (%)
  - 毎週水曜 15:30 UTC (木曜 00:30 JST)

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests
import xlrd

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "us_gasoline_inventories_refinery_utilization_cache.json"

REDIS_KEY = "market:us_gasoline_inventories_refinery_utilization:data"

# Two separate EIA XLS files
GASOLINE_URL = "https://www.eia.gov/dnav/pet/xls/PET_STOC_WSTK_DCU_NUS_W.xls"
REFINERY_URL = "https://www.eia.gov/dnav/pet/xls/PET_PNP_WIUP_DCU_NUS_W.xls"

GASOLINE_SERIES_ID = "WGTSTUS1"
REFINERY_SERIES_ID = "WPULEUS3"

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


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
        """FMPから次回EIA発表日を取得"""
        try:
            from services.usa.fmp_next_release_utils import get_next_release_from_fmp
            return get_next_release_from_fmp("us_gasoline_inventories_refinery_utilization_rate")
        except Exception as e:
            logger.error(f"[GasolineRefinery] Next release error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIAから2つのXLSをダウンロードしてマージ"""
        logger.info("[GasolineRefinery] Building data from EIA XLS...")

        # Download both XLS files
        gasoline_bytes = self._download_xls(GASOLINE_URL, "Gasoline")
        refinery_bytes = self._download_xls(REFINERY_URL, "Refinery")

        if not gasoline_bytes and not refinery_bytes:
            logger.error("[GasolineRefinery] Failed to download both XLS files")
            return None

        # Parse each XLS
        gasoline_map: Dict[str, float] = {}
        refinery_map: Dict[str, float] = {}

        if gasoline_bytes:
            gasoline_map = self._parse_single_series(
                gasoline_bytes, GASOLINE_SERIES_ID, "Gasoline"
            )

        if refinery_bytes:
            refinery_map = self._parse_single_series(
                refinery_bytes, REFINERY_SERIES_ID, "Refinery"
            )

        if not gasoline_map and not refinery_map:
            logger.error("[GasolineRefinery] No data parsed from either XLS")
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
            f"[GasolineRefinery] Parsed {len(result_data)} data points "
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

    def _download_xls(self, url: str, label: str) -> Optional[bytes]:
        """EIAからXLSファイルをダウンロード"""
        try:
            logger.info(f"[GasolineRefinery] Downloading {label}: {url}")
            resp = requests.get(url, timeout=30, headers=HTTP_HEADERS)
            if resp.status_code == 200 and len(resp.content) > 10000:
                logger.info(f"[GasolineRefinery] {label}: {len(resp.content)} bytes")
                return resp.content
            else:
                logger.error(
                    f"[GasolineRefinery] {label} download failed: "
                    f"status={resp.status_code}, size={len(resp.content)}"
                )
        except Exception as e:
            logger.error(f"[GasolineRefinery] {label} download error: {e}")
        return None

    def _parse_single_series(
        self, xls_bytes: bytes, series_id: str, label: str
    ) -> Dict[str, float]:
        """XLSファイルから単一系列を抽出してdate→valueのマップを返す"""
        try:
            wb = xlrd.open_workbook(file_contents=xls_bytes)
        except Exception as e:
            logger.error(f"[GasolineRefinery] {label} XLS parse error: {e}")
            return {}

        # Find "Data 1" sheet
        try:
            ws = wb.sheet_by_name("Data 1")
        except xlrd.XLRDError:
            if wb.nsheets > 1:
                ws = wb.sheet_by_index(1)
            else:
                logger.error(f"[GasolineRefinery] {label}: 'Data 1' sheet not found")
                return {}

        # Row 1: source keys → find column index
        source_keys_row = ws.row_values(1)
        target_col: Optional[int] = None
        for col_idx, key in enumerate(source_keys_row):
            if str(key).strip() == series_id:
                target_col = col_idx
                break

        if target_col is None:
            logger.error(
                f"[GasolineRefinery] {label}: series {series_id} not found in row 1"
            )
            return {}

        logger.info(f"[GasolineRefinery] {label}: {series_id} at col {target_col}")

        result: Dict[str, float] = {}
        for row_idx in range(3, ws.nrows):
            if ws.cell_type(row_idx, 0) != xlrd.XL_CELL_DATE:
                continue

            date_tuple = xlrd.xldate_as_tuple(ws.cell_value(row_idx, 0), wb.datemode)
            date_str = f"{date_tuple[0]:04d}-{date_tuple[1]:02d}-{date_tuple[2]:02d}"

            cell_type = ws.cell_type(row_idx, target_col)
            if cell_type in (xlrd.XL_CELL_NUMBER, xlrd.XL_CELL_TEXT):
                try:
                    val = float(ws.cell_value(row_idx, target_col))
                    result[date_str] = val
                except (ValueError, TypeError):
                    pass

        logger.info(f"[GasolineRefinery] {label}: parsed {len(result)} data points")
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
