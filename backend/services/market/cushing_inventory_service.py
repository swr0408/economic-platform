"""
米国クッシング原油在庫 (EIA Cushing, OK Crude Oil Stocks) サービス

データソース:
  - EIA: 週次Excelファイル (XLS)
  - URL: https://www.eia.gov/dnav/pet/xls/PET_STOC_WSTK_DCU_YCUOK_W.xls
  - 毎週水曜 15:30 UTC (木曜 00:30 JST)

1系列:
  - W_EPC0_SAX_YCUOK_MBBL: Cushing, OK Ending Stocks excl SPR (千バレル)

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
DATA_CACHE_FILE = CACHE_DIR / "cushing_inventory_cache.json"

REDIS_KEY = "market:cushing_inventory:data"

EIA_URL = "https://www.eia.gov/dnav/pet/xls/PET_STOC_WSTK_DCU_YCUOK_W.xls"

# Target series ID
TARGET_SERIES_KEY = "W_EPC0_SAX_YCUOK_MBBL"


class CushingInventoryService:
    """EIA 米国クッシング原油在庫サービス"""

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
            logger.error(f"[CushingInv] Build error: {e}")
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
        """FMPから次回EIAクッシング在庫発表日を取得"""
        try:
            from services.usa.fmp_next_release_utils import get_next_release_from_fmp
            return get_next_release_from_fmp("us_cushing_inventory")
        except Exception as e:
            logger.error(f"[CushingInv] Next release error: {e}")
            return None

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """EIAからXLSをダウンロードしてパース"""
        logger.info("[CushingInv] Building data from EIA XLS...")

        xls_bytes = self._download_xls()
        if not xls_bytes:
            logger.error("[CushingInv] Failed to download XLS")
            return None

        return self._parse_xls(xls_bytes)

    def _download_xls(self) -> Optional[bytes]:
        try:
            logger.info(f"[CushingInv] Downloading {EIA_URL}")
            resp = requests.get(EIA_URL, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code == 200 and len(resp.content) > 5000:
                logger.info(f"[CushingInv] Downloaded {len(resp.content)} bytes")
                return resp.content
            else:
                logger.error(
                    f"[CushingInv] Download failed: status={resp.status_code}, "
                    f"size={len(resp.content)}"
                )
        except Exception as e:
            logger.error(f"[CushingInv] Download error: {e}")
        return None

    def _parse_xls(self, xls_bytes: bytes) -> Optional[Dict[str, Any]]:
        """XLSファイルをパース

        構造:
          - Sheet "Data 1"
          - Row 0: ナビゲーション
          - Row 1: ソースキー (W_EPC0_SAX_YCUOK_MBBL)
          - Row 2: 説明
          - Row 3+: データ (col 0=日付, col 1=値)
        """
        try:
            wb = xlrd.open_workbook(file_contents=xls_bytes)
        except Exception as e:
            logger.error(f"[CushingInv] XLS parse error: {e}")
            return None

        try:
            ws = wb.sheet_by_name("Data 1")
        except xlrd.XLRDError:
            if wb.nsheets > 1:
                ws = wb.sheet_by_index(1)
            else:
                logger.error("[CushingInv] 'Data 1' sheet not found")
                return None

        # Row 1: source keys → find column index
        source_keys_row = ws.row_values(1)
        value_col = None
        for col_idx, key in enumerate(source_keys_row):
            if str(key).strip() == TARGET_SERIES_KEY:
                value_col = col_idx
                break

        if value_col is None:
            # Fallback: use column 1 (only 2 columns in this file)
            value_col = 1
            logger.warning(
                f"[CushingInv] Target series key not found, using col {value_col}"
            )

        result_data: List[Dict[str, Any]] = []

        for row_idx in range(3, ws.nrows):
            date_cell_type = ws.cell_type(row_idx, 0)
            if date_cell_type != xlrd.XL_CELL_DATE:
                continue

            date_tuple = xlrd.xldate_as_tuple(ws.cell_value(row_idx, 0), wb.datemode)
            date_str = f"{date_tuple[0]:04d}-{date_tuple[1]:02d}-{date_tuple[2]:02d}"

            cell_type = ws.cell_type(row_idx, value_col)
            if cell_type in (xlrd.XL_CELL_NUMBER, xlrd.XL_CELL_TEXT):
                try:
                    val = round(float(ws.cell_value(row_idx, value_col)), 0)
                except (ValueError, TypeError):
                    val = None
            else:
                val = None

            if val is None:
                continue

            result_data.append({
                "date": date_str,
                "value": val,
            })

        if not result_data:
            logger.error("[CushingInv] No data parsed from XLS")
            return None

        result_data.sort(key=lambda x: x["date"])

        # Calculate YoY (前年比) using 52-week lookback
        date_idx_map = {d["date"]: i for i, d in enumerate(result_data)}
        for item in result_data:
            val = item["value"]
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
                prev_val = result_data[best_match]["value"]
                if prev_val and prev_val != 0:
                    yoy_pct = ((val - prev_val) / prev_val) * 100
                    item["yoy"] = round(yoy_pct, 2)
                else:
                    item["yoy"] = None
            else:
                item["yoy"] = None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[CushingInv] Parsed {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest value={latest.get('value')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "EIA",
                "frequency": "weekly",
                "unit": "Thousand Barrels",
                "series": "Cushing, OK Ending Stocks excl SPR of Crude Oil",
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
            logger.error(f"[CushingInv] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[CushingInv] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[CushingInv] Redis load error: {e}")
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
            logger.error(f"[CushingInv] File load error: {e}")
        return None


cushing_inventory_service = CushingInventoryService()
