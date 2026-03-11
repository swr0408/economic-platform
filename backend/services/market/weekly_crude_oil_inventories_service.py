"""
週間原油在庫 (EIA Weekly Crude Oil Inventories) サービス

データソース:
  - EIA: 週次Excelファイル (XLS)
  - URL: https://www.eia.gov/dnav/pet/xls/PET_STOC_WSTK_DCU_NUS_W.xls
  - 毎週水曜 15:30 UTC (木曜 00:30 JST)

3系列:
  - WCRSTUS1: 原油在庫合計 (千バレル)
  - WCESTUS1: 原油在庫 SPR除く (千バレル)
  - WCSSTUS1: SPR在庫 (千バレル)

更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
from datetime import datetime, timedelta
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
DATA_CACHE_FILE = CACHE_DIR / "weekly_crude_oil_inventories_cache.json"

REDIS_KEY = "market:weekly_crude_oil_inventories:data"

EIA_URL = "https://www.eia.gov/dnav/pet/xls/PET_STOC_WSTK_DCU_NUS_W.xls"

# Target series IDs and their column indices (0-indexed in the data sheet)
# Row 1 contains source keys: col 0=date, col 1..N = series IDs
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
        """EIAからXLSをダウンロードしてパース"""
        logger.info("[CrudeOilInv] Building data from EIA XLS...")

        xls_bytes = self._download_xls()
        if not xls_bytes:
            logger.error("[CrudeOilInv] Failed to download XLS")
            return None

        return self._parse_xls(xls_bytes)

    def _download_xls(self) -> Optional[bytes]:
        """EIAからXLSファイルをダウンロード"""
        try:
            logger.info(f"[CrudeOilInv] Downloading {EIA_URL}")
            resp = requests.get(EIA_URL, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code == 200 and len(resp.content) > 10000:
                logger.info(f"[CrudeOilInv] Downloaded {len(resp.content)} bytes")
                return resp.content
            else:
                logger.error(
                    f"[CrudeOilInv] Download failed: status={resp.status_code}, "
                    f"size={len(resp.content)}"
                )
        except Exception as e:
            logger.error(f"[CrudeOilInv] Download error: {e}")
        return None

    def _parse_xls(self, xls_bytes: bytes) -> Optional[Dict[str, Any]]:
        """XLSファイルをパース

        構造:
          - Sheet "Data 1"
          - Row 0: ナビゲーション
          - Row 1: ソースキー (WCRSTUS1, WCESTUS1, ...)
          - Row 2: 説明
          - Row 3+: データ (col 0=日付, col N=値)
        """
        try:
            wb = xlrd.open_workbook(file_contents=xls_bytes)
        except Exception as e:
            logger.error(f"[CrudeOilInv] XLS parse error: {e}")
            return None

        # Find "Data 1" sheet
        try:
            ws = wb.sheet_by_name("Data 1")
        except xlrd.XLRDError:
            if wb.nsheets > 1:
                ws = wb.sheet_by_index(1)
            else:
                logger.error("[CrudeOilInv] 'Data 1' sheet not found")
                return None

        # Row 1: source keys → find column indices for target series
        source_keys_row = ws.row_values(1)
        col_map: Dict[str, int] = {}
        for col_idx, key in enumerate(source_keys_row):
            key_str = str(key).strip()
            if key_str in TARGET_SERIES:
                col_map[key_str] = col_idx

        if len(col_map) < 3:
            logger.error(
                f"[CrudeOilInv] Missing series columns. Found: {list(col_map.keys())}"
            )
            return None

        logger.info(f"[CrudeOilInv] Column mapping: {col_map}")

        result_data: List[Dict[str, Any]] = []

        for row_idx in range(3, ws.nrows):
            # Date in col 0
            date_cell_type = ws.cell_type(row_idx, 0)
            if date_cell_type != xlrd.XL_CELL_DATE:
                continue

            date_tuple = xlrd.xldate_as_tuple(ws.cell_value(row_idx, 0), wb.datemode)
            date_str = f"{date_tuple[0]:04d}-{date_tuple[1]:02d}-{date_tuple[2]:02d}"

            item: Dict[str, Any] = {"date": date_str}

            for series_id, field_name in TARGET_SERIES.items():
                col = col_map.get(series_id)
                if col is None:
                    item[field_name] = None
                    continue
                cell_type = ws.cell_type(row_idx, col)
                if cell_type in (xlrd.XL_CELL_NUMBER, xlrd.XL_CELL_TEXT):
                    try:
                        val = float(ws.cell_value(row_idx, col))
                        item[field_name] = round(val, 0)
                    except (ValueError, TypeError):
                        item[field_name] = None
                else:
                    item[field_name] = None

            # Skip rows with no values
            if all(item.get(f) is None for f in TARGET_SERIES.values()):
                continue

            result_data.append(item)

        if not result_data:
            logger.error("[CrudeOilInv] No data parsed from XLS")
            return None

        # Sort ascending by date
        result_data.sort(key=lambda x: x["date"])

        # Calculate YoY (前年比) for each series
        # Build date index map for ~52 week lookback
        date_idx_map = {d["date"]: i for i, d in enumerate(result_data)}
        for i, item in enumerate(result_data):
            for field in TARGET_SERIES.values():
                val = item.get(field)
                if val is None:
                    item[f"{field}_yoy"] = None
                    continue

                # Find same week last year (52 weeks = 364 days back)
                current_date = datetime.strptime(item["date"], "%Y-%m-%d")
                target_date = current_date - timedelta(days=364)

                # Search for closest date within ±7 days
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
            f"[CrudeOilInv] Parsed {len(result_data)} data points "
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
