"""
Japan Industrial Production Index (IIP) YoY Service
Fetches raw index (原指数) from METI and calculates YoY

Data source: Ministry of Economy, Trade and Industry (METI)
URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_gom1j.xlsx (原指数)
Calculation: ((current_month - same_month_last_year) / same_month_last_year) * 100
"""
import json
import logging
import io
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

try:
    from backend.core.redis_client import redis_client
    from backend.services.japan.estat_file_source import download_estat_excel
except ImportError:
    from core.redis_client import redis_client
    from services.japan.estat_file_source import download_estat_excel

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_iip_yoy_cache.json"


class JapanIIPYoYService:
    """Service for fetching raw IIP index and calculating YoY data"""

    # 取得元: e-Stat の「品目別／月次／原指数」の '生産' シート(YoY 算出用の原指数)。
    # www.meti.go.jp は当サーバ IP をブロックするため e-Stat へ移行(旧 b2020_gom1j.xlsx と同構造)。
    ESTAT_STATS_CODE = "00550300"
    ESTAT_TABLE_FILTER = "品目別／月次／原指数"
    ESTAT_FALLBACK_IDS = ("000040172368",)

    DATA_CACHE_KEY = "japan:iip_yoy:data"

    def __init__(self):
        pass

    def _download_excel_file(self) -> Optional[bytes]:
        """e-Stat から IIP 原指数(品目別/月次)の Excel を取得する(YoY 算出用)。

        statInfId はリリース毎にローテートするため Data Catalog API で動的解決する。
        取得不能時は None(呼び出し側がキャッシュにフォールバック)。
        """
        return download_estat_excel(
            stats_code=self.ESTAT_STATS_CODE,
            table_name_filter=self.ESTAT_TABLE_FILTER,
            fallback_stat_inf_ids=self.ESTAT_FALLBACK_IDS,
        )

    def _parse_raw_index_excel(self, excel_content: bytes) -> Optional[Dict[str, float]]:
        """
        Parse raw index values from Excel file (原指数)

        Returns:
            Dictionary mapping date -> raw index value
        """
        try:
            excel_file = io.BytesIO(excel_content)
            xl = pd.ExcelFile(excel_file)
            logger.info(f"Excel has {len(xl.sheet_names)} sheets")

            # Read the second sheet (生産 / Production)
            df = pd.read_excel(excel_file, sheet_name=xl.sheet_names[1], header=None)
            logger.info(f"Sheet shape: {df.shape}")

            # Standard structure
            HEADER_ROW = 2
            DATA_START_ROW = 3
            ITEM_CODE_COL = 0
            DATA_START_COL = 3

            # Get date headers
            header_row = df.iloc[HEADER_ROW]

            # Find row with item code 1000000000 (鉱工業)
            target_row_idx = None
            for row_idx in range(DATA_START_ROW, min(DATA_START_ROW + 50, len(df))):
                row = df.iloc[row_idx]
                if not pd.isna(row[ITEM_CODE_COL]):
                    try:
                        item_code = str(int(float(row[ITEM_CODE_COL])))
                        if item_code == '1000000000':
                            target_row_idx = row_idx
                            break
                    except (ValueError, TypeError):
                        continue

            if target_row_idx is None:
                logger.error("Could not find item code 1000000000 (鉱工業)")
                return None

            row = df.iloc[target_row_idx]
            logger.info(f"Found 鉱工業 at row {target_row_idx}")

            # Extract monthly raw index values
            monthly_data = {}
            for col_idx in range(DATA_START_COL, len(row)):
                try:
                    date_header = header_row[col_idx]
                    if pd.isna(date_header):
                        continue

                    index_value = row[col_idx]
                    if pd.isna(index_value):
                        continue

                    # Parse date (format: 201801.0 = 2018年1月, or "p 202511" for preliminary)
                    date_str_raw = str(date_header).strip()

                    # Handle preliminary data prefix (e.g., "p 202511")
                    if date_str_raw.startswith('p '):
                        date_str_raw = date_str_raw[2:]  # Remove "p " prefix

                    date_num = int(float(date_str_raw))
                    year = date_num // 100
                    month = date_num % 100

                    if year > 1900 and 1 <= month <= 12:
                        date_str = f"{year}-{month:02d}-01"
                        monthly_data[date_str] = float(index_value)

                except (ValueError, TypeError, IndexError):
                    continue

            logger.info(f"Extracted {len(monthly_data)} monthly raw index values")
            return monthly_data

        except Exception as e:
            logger.error(f"Error parsing raw index Excel: {e}", exc_info=True)
            return None

    def _calculate_yoy_from_raw_index(self, raw_index_data: Dict[str, float]) -> Optional[List[Dict]]:
        """
        Calculate YoY from raw index values
        """
        try:
            yoy_data = []

            for date_str, current_value in raw_index_data.items():
                year, month, _ = date_str.split('-')
                year = int(year)
                month = int(month)

                # Get same month last year
                last_year_date = f"{year - 1}-{month:02d}-01"

                yoy_change = None
                if last_year_date in raw_index_data:
                    last_year_value = raw_index_data[last_year_date]
                    if last_year_value != 0:
                        yoy_change = ((current_value - last_year_value) / last_year_value) * 100

                yoy_data.append({
                    "date": date_str,
                    "item_code": "1000000000",
                    "item_name": "鉱工業",
                    "category": "鉱工業",
                    "index_value": current_value,
                    "yoy_change": yoy_change
                })

            # Sort by date (most recent first)
            yoy_data.sort(key=lambda x: x['date'], reverse=True)

            logger.info(f"Calculated YoY for {len(yoy_data)} data points from raw index")
            if yoy_data:
                logger.info(f"Sample (first 3): {yoy_data[:3]}")

            return yoy_data

        except Exception as e:
            logger.error(f"Error calculating YoY: {e}", exc_info=True)
            return None

    def _fetch_iip_yoy_data(self) -> Optional[Dict[str, Any]]:
        """
        Fetch raw IIP index and calculate YoY data
        """
        try:
            logger.info("Fetching Japan IIP YoY data from raw index (原指数)")

            excel_content = self._download_excel_file()
            if not excel_content:
                logger.error("Failed to download raw index Excel file")
                return None

            raw_index_data = self._parse_raw_index_excel(excel_content)
            if not raw_index_data:
                logger.error("Failed to parse raw index data")
                return None

            yoy_data_points = self._calculate_yoy_from_raw_index(raw_index_data)
            if not yoy_data_points:
                logger.error("Failed to calculate YoY data")
                return None

            processed_data = []
            for item in yoy_data_points:
                processed_data.append({
                    "date": item['date'],
                    "item_code": item['item_code'],
                    "item_name": item['item_name'],
                    "category": item['category'],
                    "index_value": round(item['index_value'], 1) if item['index_value'] is not None else None,
                    "yoy_change": round(item['yoy_change'], 2) if item['yoy_change'] is not None else None
                })

            return {
                "data": processed_data,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Ministry of Economy, Trade and Industry (METI) - Raw index (原指数)"
            }

        except Exception as e:
            logger.error(f"Error fetching IIP YoY data: {e}", exc_info=True)
            return None

    def get_iip_yoy_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get Japan IIP YoY data with caching.

        Strategy:
        1. Fresh cache hit → return immediately.
        2. Circuit breaker: if METI failed in the last 5 minutes, skip fetch and serve stale cache.
        3. Otherwise try METI; on success update both caches and clear breaker.
        4. On failure set breaker (5 min cooldown) and fall back to Redis → file cache → empty.
        """
        cached_data = redis_client.get(self.DATA_CACHE_KEY)
        negative_key = self.DATA_CACHE_KEY + ":fetch_failed"

        # 1) Fresh cache hit
        if not force_refresh and cached_data:
            last_updated_str = cached_data.get("last_updated")
            if last_updated_str and not self._should_refresh(last_updated_str):
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("data", [{}])[0] if cached_data.get("data") else None,
                    "cached": True,
                    "source": "redis",
                    "last_updated": last_updated_str
                }

        # 2) Circuit breaker: recent METI failure → skip fetch, serve any cache
        if not force_refresh and redis_client.exists(negative_key):
            if cached_data:
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("data", [{}])[0] if cached_data.get("data") else None,
                    "cached": True,
                    "source": "redis (stale, breaker)",
                    "last_updated": cached_data.get("last_updated")
                }
            file_cache = self._load_file_cache()
            if file_cache:
                return {
                    "data": file_cache.get("data", []),
                    "latest": file_cache.get("data", [{}])[0] if file_cache.get("data") else None,
                    "cached": True,
                    "source": "file (stale, breaker)",
                    "last_updated": file_cache.get("last_updated")
                }

        # 3) Try fresh fetch
        result = self._fetch_iip_yoy_data()
        if result:
            cache_payload = {
                "data": result["data"],
                "last_updated": result["last_updated"],
                "source": result["source"]
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)
            redis_client.delete(negative_key)

            return {
                "data": result["data"],
                "latest": result["data"][0] if result["data"] else None,
                "cached": False,
                "source": "meti",
                "last_updated": result["last_updated"]
            }

        # 4) Fetch failed → set breaker and serve any cache
        redis_client.set(negative_key, {"failed_at": datetime.now(JST).isoformat()}, expire=300)

        if cached_data:
            return {
                "data": cached_data.get("data", []),
                "latest": cached_data.get("data", [{}])[0] if cached_data.get("data") else None,
                "cached": True,
                "source": "redis (stale, fallback)",
                "last_updated": cached_data.get("last_updated")
            }
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("data", [{}])[0] if file_cache.get("data") else None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """Check if cache should be refreshed.

        月次指標 — 7-day freshness window aligns with release cadence and absorbs
        occasional source-API downtime without forcing every request to hit it.
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            cache_age_hours = (now - last_updated).total_seconds() / 3600

            if cache_age_hours > 24 * 7:
                return True

            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Japan Industrial Production Index (IIP) YoY",
            "source": "METI - Raw index",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("data", [{}])[0] if cached_data and cached_data.get("data") else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# Singleton instance
japan_iip_yoy_service = JapanIIPYoYService()
