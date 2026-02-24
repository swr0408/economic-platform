"""
オーストラリア 建築許可件数（Number of Building Permits）サービス

データソース:
- ABS (Australian Bureau of Statistics)
- Series ID: A422070J
  = Total dwelling units; Total (Type of Building); Total Sectors; Seasonally Adjusted
- ローカルExcelファイル（手動更新）
  - backend/data/excel/8731006_YYYYMMDD.xlsx (またはABSからDL)
- フォールバック: ABS TSSearchServlet APIで最新Excelを自動ダウンロード

手動更新: 新しい日付のExcelファイルが配置されると自動検出

発表スケジュール: 月次
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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_number_of_building_permits_cache.json"

# Excelファイル配置ディレクトリ
EXCEL_DIR = Path(__file__).parent.parent.parent / "data" / "excel"

# ファイル名パターン (ABS Building Approvals: 8731006_YYYYMMDD.xlsx)
EXCEL_PATTERN = "8731006_*.xlsx"

# Series ID A422070J の列位置（Data1シートの列14）
SERIES_ID = "A422070J"

# ABS TSSearchServlet URL（フォールバック用）
ABS_SEARCH_URL = f"https://www.abs.gov.au/servlet/TSSearchServlet?sid={SERIES_ID}"


class AuNumberOfBuildingPermitsService:
    """オーストラリア建築許可件数サービス（季節調整済み、全住戸合計）"""

    DATA_CACHE_KEY = "australia:au_number_of_building_permits:data"
    FMP_EVENT_PATTERN = "Building Permits"
    FMP_COUNTRY = "AU"

    def __init__(self):
        pass

    def _find_latest_excel(self) -> Optional[Path]:
        """最新日付のExcelファイルを自動検出"""
        files = list(EXCEL_DIR.glob(EXCEL_PATTERN))
        if not files:
            return None

        dated_files = []
        for f in files:
            match = re.search(r"(\d{8})\.xlsx$", f.name)
            if match:
                dated_files.append((match.group(1), f))

        if not dated_files:
            return None

        dated_files.sort(key=lambda x: x[0], reverse=True)
        latest_date, latest_file = dated_files[0]
        logger.info(f"Using ABS Building Permits Excel file: {latest_file.name} (date: {latest_date})")
        return latest_file

    def _download_excel_from_abs(self) -> Optional[bytes]:
        """ABS TSSearchServlet APIからExcelをダウンロード（フォールバック）"""
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

    def _parse_excel(self, source) -> List[Dict[str, Any]]:
        """Excelから建築許可件数データを抽出

        ABS Excelの構造:
        - Sheet: Data1
        - Row 9: Series IDs
        - Row 10+: Data (datetime in Col 0, values in other cols)
        - A422070J は可変列（ヘッダーで検出）
        """
        try:
            if isinstance(source, Path):
                df = pd.read_excel(source, sheet_name="Data1", header=None)
            else:
                df = pd.read_excel(io.BytesIO(source), sheet_name="Data1", header=None)

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
                    date_str = dt.strftime("%Y-%m-01")
                except (ValueError, TypeError):
                    continue

                val = df.iloc[row_idx, target_col]
                if pd.isna(val):
                    continue

                data_points.append({
                    "date": date_str,
                    "value": round(float(val), 0),
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

            logger.info(f"Parsed {len(data_points)} building permits data points")
            return data_points

        except Exception as e:
            logger.error(f"Error parsing ABS Building Permits Excel: {e}")
            return []

    def _calculate_changes(self, data_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """MoM%とYoY%を算出"""
        result = []
        date_map = {p["date"]: p["value"] for p in data_points}

        for i, point in enumerate(data_points):
            val = point["value"]
            mom = None
            yoy = None

            # MoM%
            if i >= 1:
                prev_val = data_points[i - 1]["value"]
                if prev_val is not None and prev_val != 0:
                    mom = round((val - prev_val) / prev_val * 100, 2)

            # YoY%
            dt = datetime.strptime(point["date"], "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"
            if prev_year_date in date_map:
                prev_year_val = date_map[prev_year_date]
                if prev_year_val is not None and prev_year_val != 0:
                    yoy = round((val - prev_year_val) / prev_year_val * 100, 2)

            result.append({
                "date": point["date"],
                "value": val,
                "mom": mom,
                "yoy": yoy,
            })

        return result

    def _should_refresh_by_file(self, last_updated_str: Optional[str]) -> bool:
        """新しいExcelファイルが配置されたかどうかで更新判定"""
        if last_updated_str is None:
            return True

        latest_file = self._find_latest_excel()
        if not latest_file:
            return False

        match = re.search(r"(\d{8})\.xlsx$", latest_file.name)
        if not match:
            return False

        file_date = match.group(1)

        cached_data = redis_client.get(self.DATA_CACHE_KEY)
        if cached_data:
            cached_file_date = cached_data.get("file_date", "")
            if file_date > cached_file_date:
                logger.info(f"New Building Permits file detected: {file_date} > {cached_file_date}")
                return True
        return False

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュ更新判定（FMP + ファイル両方チェック）"""
        # ファイルベース判定
        if self._should_refresh_by_file(last_updated_str):
            return True
        # FMP発表日ベース判定
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
                month_match = re.search(r"\((\w+)\)", label)
                month_str = month_match.group(1) if month_match else ""
                result["label"] = f"建築許可件数 ({month_str})".strip()
            return result
        except Exception as e:
            logger.warning(f"Failed to get next release: {e}")
            return None

    def get_au_number_of_building_permits_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """建築許可件数データを取得（キャッシュ付き）"""
        next_release = self._get_next_release()

        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                    }

        # 1. ローカルExcelから取得を試行
        raw_data = None
        source_type = "local_excel"
        file_date = ""

        excel_file = self._find_latest_excel()
        if excel_file:
            raw_data = self._parse_excel(excel_file)
            match = re.search(r"(\d{8})\.xlsx$", excel_file.name)
            if match:
                file_date = match.group(1)
        else:
            # 2. ABS APIからExcelをダウンロード（フォールバック）
            logger.info("No local Excel found, trying ABS API download...")
            excel_bytes = self._download_excel_from_abs()
            if excel_bytes:
                raw_data = self._parse_excel(excel_bytes)
                source_type = "abs_api"
                file_date = datetime.now(JST).strftime("%Y%m%d")

        if raw_data:
            data_with_changes = self._calculate_changes(raw_data)
            latest = data_with_changes[-1] if data_with_changes else None

            result = {
                "data": data_with_changes,
                "latest": latest,
                "metadata": {
                    "source": "Australian Bureau of Statistics",
                    "indicator": "Number of Building Permits (Seasonally Adjusted)",
                    "frequency": "monthly",
                    "unit": "units",
                    "series_id": SERIES_ID,
                },
                "next_release": next_release,
            }
            cache_payload = {
                **result,
                "last_updated": datetime.now(JST).isoformat(),
                "file_date": file_date,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)
            return {**result, "cached": False, "source": source_type}

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
            }

        return {
            "data": [], "latest": None,
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
        latest_file = self._find_latest_excel()
        return {
            "indicator": "AU Number of Building Permits (Seasonally Adjusted)",
            "source": "ABS Excel",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_date": cached_data.get("file_date") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "latest_excel_file": latest_file.name if latest_file else None,
            "next_release": self._get_next_release(),
        }


au_number_of_building_permits_service = AuNumberOfBuildingPermitsService()
