"""
オーストラリア 経常収支（Current Account）サービス

データソース:
- ABS (Australian Bureau of Statistics)
- Product: 5302.0 Balance of Payments and International Investment Position
- Table 4: Current Account Transactions (Seasonally Adjusted)
- Series ID: A3535187L = Current account ; Seasonally Adjusted
- 単位: $ Millions → B AUD に変換して格納

取得方法:
1. ABS TSSearchServlet API → TableURL(xlsx) を取得
2. Excel (Data1シート, Row 9 = Series ID行, Row 10+ = データ行)

発表スケジュール: 四半期
"""
import io
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_current_account_cache.json"

# Series ID
SERIES_ID = "A3535187L"

# ABS TSSearchServlet URL
ABS_SEARCH_URL = f"https://www.abs.gov.au/servlet/TSSearchServlet?sid={SERIES_ID}"


class AuCurrentAccountService:
    """オーストラリア経常収支サービス（季節調整済み、四半期）"""

    DATA_CACHE_KEY = "australia:au_current_account:data"
    FMP_EVENT_PATTERN = "Current Account"
    FMP_COUNTRY = "AU"

    def __init__(self):
        pass

    def _download_excel_from_abs(self) -> Optional[bytes]:
        """ABS TSSearchServlet APIからExcelをダウンロード"""
        try:
            logger.info(f"Fetching ABS metadata from {ABS_SEARCH_URL}")
            resp = requests.get(ABS_SEARCH_URL, timeout=30)
            if resp.status_code != 200:
                logger.error(f"ABS TSSearchServlet returned HTTP {resp.status_code}")
                return None

            root = ET.fromstring(resp.text)
            table_url = None
            for elem in root.iter():
                if elem.tag == "TableURL" and elem.text:
                    table_url = elem.text.strip()
                    break

            if not table_url:
                logger.error("No TableURL found in ABS TSSearchServlet response")
                return None

            logger.info(f"Downloading ABS Excel from {table_url}")
            excel_resp = requests.get(table_url, timeout=60)
            if excel_resp.status_code != 200:
                logger.error(f"ABS Excel download returned HTTP {excel_resp.status_code}")
                return None

            return excel_resp.content

        except Exception as e:
            logger.error(f"Error downloading ABS Excel: {e}")
            return None

    def _parse_excel(self, excel_bytes: bytes) -> List[Dict[str, Any]]:
        """Excelから経常収支データを抽出

        ABS Excelの構造:
        - Sheet: Data1
        - Row 9: Series IDs
        - Row 10+: Data (datetime in Col 0, values in other cols)
        - A3535187L = Current account ($ Millions)
        """
        try:
            df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name="Data1", header=None)

            # Row 9でSeries IDの列を特定
            target_col = None
            for col_idx in range(df.shape[1]):
                cell_val = df.iloc[9, col_idx] if 9 < df.shape[0] else None
                if cell_val is not None and str(cell_val).strip() == SERIES_ID:
                    target_col = col_idx
                    break

            if target_col is None:
                logger.error(f"Series ID {SERIES_ID} not found in Row 9")
                return []

            logger.info(f"Found {SERIES_ID} at column {target_col}")

            data_points = []
            for row_idx in range(10, df.shape[0]):
                date_val = df.iloc[row_idx, 0]
                if pd.isna(date_val):
                    continue

                try:
                    if isinstance(date_val, (datetime, pd.Timestamp)):
                        dt = date_val
                    elif isinstance(date_val, str):
                        dt = datetime.strptime(date_val, "%Y-%m-%d")
                    else:
                        continue
                    # 四半期の開始月で正規化（3,6,9,12月）
                    date_str = dt.strftime("%Y-%m-01")
                except (ValueError, TypeError):
                    continue

                val = df.iloc[row_idx, target_col]
                if pd.isna(val):
                    continue

                # $ Millions → B AUD (÷ 1000)
                value_b = round(float(val) / 1000, 3)

                data_points.append({
                    "date": date_str,
                    "value": value_b,
                })

            data_points.sort(key=lambda x: x["date"])

            # 重複日付除去（後の値を優先）
            seen = set()
            unique = []
            for p in reversed(data_points):
                if p["date"] not in seen:
                    seen.add(p["date"])
                    unique.append(p)
            unique.reverse()
            data_points = unique

            logger.info(f"Parsed {len(data_points)} current account data points")
            return data_points

        except Exception as e:
            logger.error(f"Error parsing ABS Current Account Excel: {e}")
            return []

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """QoQ差分とYoY差分を算出

        Returns:
            {
                "qoq_diff": [{"date": ..., "value": ...}, ...],  # 前期差分 (B AUD)
                "yoy_diff": [{"date": ..., "value": ...}, ...],  # 前年同期差分 (B AUD)
            }
        """
        qoq_diff = []
        yoy_diff = []
        date_map = {p["date"]: p["value"] for p in data}

        for i, point in enumerate(data):
            val = point["value"]

            # QoQ差分（前四半期との差）
            if i >= 1:
                prev_val = data[i - 1]["value"]
                if prev_val is not None:
                    qoq_diff.append({
                        "date": point["date"],
                        "value": round(val - prev_val, 3),
                    })

            # YoY差分（前年同期との差）
            dt = datetime.strptime(point["date"], "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"
            if prev_year_date in date_map:
                prev_year_val = date_map[prev_year_date]
                if prev_year_val is not None:
                    yoy_diff.append({
                        "date": point["date"],
                        "value": round(val - prev_year_val, 3),
                    })

        return {"qoq_diff": qoq_diff, "yoy_diff": yoy_diff}

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定（FMP発表日ベース）"""
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

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        """次回発表日を取得"""
        try:
            from services.australia.fmp_next_release_utils import get_next_release_by_pattern
            result = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)
            if result:
                label = result.get("label", "")
                quarter_match = re.search(r"\((\w+)\)", label)
                quarter_str = quarter_match.group(1) if quarter_match else ""
                result["label"] = f"経常収支 ({quarter_str})".strip()
            return result
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def get_au_current_account_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """経常収支データを取得（キャッシュ付き）"""
        next_release = self._get_next_release()

        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "qoq_diff": cached_data.get("qoq_diff", []),
                        "yoy_diff": cached_data.get("yoy_diff", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                    }

        # ABS APIからExcelをダウンロード
        excel_bytes = self._download_excel_from_abs()
        if excel_bytes:
            raw_data = self._parse_excel(excel_bytes)
            if raw_data:
                changes = self._calculate_changes(raw_data)
                latest = raw_data[-1] if raw_data else None
                from services.usa.fmp_next_release_utils import guarded_last_updated
                _now_lu = datetime.now(JST).isoformat()
                _lu = guarded_last_updated(self.DATA_CACHE_KEY, latest.get("date") if latest else None, _now_lu)

                result = {
                    "data": raw_data,
                    "qoq_diff": changes["qoq_diff"],
                    "yoy_diff": changes["yoy_diff"],
                    "latest": latest,
                    "metadata": {
                        "source": "Australian Bureau of Statistics",
                        "indicator": "Current Account (Seasonally Adjusted)",
                        "frequency": "quarterly",
                        "unit": "B AUD (Billion AUD)",
                        "series_id": SERIES_ID,
                    },
                    "next_release": next_release,
                }
                cache_payload = {
                    **result,
                    "last_updated": _lu,
                }
                redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                self._save_file_cache(cache_payload)

                logger.info(f"AU Current Account: {len(raw_data)} records")
                if latest:
                    logger.info(f"Latest: {latest['date']} = {latest['value']:.3f} B AUD")

                return {**result, "cached": False, "source": "abs_api"}

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "qoq_diff": file_cache.get("qoq_diff", []),
                "yoy_diff": file_cache.get("yoy_diff", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
            }

        return {
            "data": [], "qoq_diff": [], "yoy_diff": [],
            "latest": None,
            "metadata": {"source": "Australian Bureau of Statistics", "error": "No data available"},
            "next_release": next_release, "cached": False, "source": "none",
        }

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
            "indicator": "AU Current Account",
            "source": "ABS (5302.0 Table 4)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "next_release": self._get_next_release(),
        }


au_current_account_service = AuCurrentAccountService()
