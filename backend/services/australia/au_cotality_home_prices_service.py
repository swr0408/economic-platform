"""
オーストラリア Cotality住宅価格指数（Home Value Index）サービス

データソース:
- Cotality (旧 CoreLogic) Daily Home Value Index
- ローカルExcelファイル（手動更新）
- backend/data/excel/Cotality_HVI_365_days_YYYYMMDD.xlsx

対象: 5 capital city aggregate (AUSD) のみ
- 日次インデックス値 + 月次MoM%/YoY%を算出

手動更新: 新しい日付のExcelファイルが配置されると自動検出

発表スケジュール: 日次（ファイル手動更新）
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "au_cotality_home_prices_cache.json"

# Excelファイル配置ディレクトリ
EXCEL_DIR = Path(__file__).parent.parent.parent / "data" / "excel"

# ファイル名パターン
EXCEL_PATTERN = "Cotality_HVI_365_days_*.xlsx"

# 5 capital city aggregate は Col 6
AGGREGATE_COL = 6


class AuCotalityHomePricesService:
    """オーストラリア Cotality住宅価格指数サービス（5 Capital City Aggregate）"""

    DATA_CACHE_KEY = "australia:au_cotality_home_prices:data"

    def __init__(self):
        pass

    def _find_latest_excel(self) -> Optional[Path]:
        """最新日付のExcelファイルを自動検出"""
        files = list(EXCEL_DIR.glob(EXCEL_PATTERN))
        if not files:
            logger.warning("No Cotality Excel files found in %s", EXCEL_DIR)
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
        logger.info(f"Using Cotality Excel file: {latest_file.name} (date: {latest_date})")
        return latest_file

    def _parse_excel(self, file_path: Path) -> List[Dict[str, Any]]:
        """Excelから5 Capital City Aggregateのインデックス値を抽出"""
        try:
            df = pd.read_excel(file_path, sheet_name="Index Values", header=None)

            data_points = []
            # Row 4以降がデータ
            for row_idx in range(4, df.shape[0]):
                date_val = df.iloc[row_idx, 0]
                if pd.isna(date_val):
                    continue

                try:
                    if isinstance(date_val, str):
                        dt = datetime.strptime(date_val, "%d/%m/%Y")
                    elif isinstance(date_val, datetime):
                        dt = date_val
                    else:
                        continue
                    date_str = dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    continue

                val = df.iloc[row_idx, AGGREGATE_COL]
                if pd.isna(val):
                    continue

                data_points.append({
                    "date": date_str,
                    "value": round(float(val), 2),
                })

            data_points.sort(key=lambda x: x["date"])
            logger.info(f"Parsed {len(data_points)} aggregate data points from Cotality Excel")
            return data_points

        except Exception as e:
            logger.error(f"Error parsing Cotality Excel: {e}")
            return []

    def _build_monthly_data(self, daily_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """日次データから月次データを構築（月末値 + MoM%）"""
        if not daily_data:
            return []

        # 月ごとに最後のデータポイントを取得
        monthly_map: Dict[str, Dict[str, Any]] = {}
        for point in daily_data:
            month_key = point["date"][:7]  # YYYY-MM
            monthly_map[month_key] = point

        months = sorted(monthly_map.keys())
        result = []

        for i, month in enumerate(months):
            point = monthly_map[month]
            val = point["value"]

            # MoM%
            mom = None
            if i >= 1 and val is not None:
                prev_val = monthly_map[months[i - 1]]["value"]
                if prev_val is not None and prev_val != 0:
                    mom = round((val - prev_val) / prev_val * 100, 2)

            result.append({
                "date": point["date"],
                "value": val,
                "mom": mom,
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
                logger.info(f"New Cotality file detected: {file_date} > {cached_file_date}")
                return True
        return False

    def get_au_cotality_home_prices_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Cotality住宅価格指数データを取得（キャッシュ付き）"""
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh_by_file(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "monthly_data": cached_data.get("monthly_data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                    }

        excel_file = self._find_latest_excel()
        if excel_file:
            daily_data = self._parse_excel(excel_file)
            if daily_data:
                monthly_data = self._build_monthly_data(daily_data)
                latest = daily_data[-1] if daily_data else None

                file_date = ""
                match = re.search(r"(\d{8})\.xlsx$", excel_file.name)
                if match:
                    file_date = match.group(1)

                result = {
                    "data": daily_data,
                    "monthly_data": monthly_data,
                    "latest": latest,
                    "metadata": {
                        "source": "Cotality (formerly CoreLogic)",
                        "indicator": "Daily Home Value Index - 5 Capital City Aggregate",
                        "frequency": "daily",
                        "unit": "index",
                    },
                    "next_release": None,
                }
                cache_payload = {
                    **result,
                    "last_updated": datetime.now(JST).isoformat(),
                    "file_date": file_date,
                }
                redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
                self._save_file_cache(cache_payload)
                return {**result, "cached": False, "source": "excel"}

        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "monthly_data": file_cache.get("monthly_data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
            }

        return {
            "data": [], "monthly_data": [], "latest": None,
            "metadata": {"source": "Cotality", "error": "No data available"},
            "next_release": None, "cached": False, "source": "none",
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
            "indicator": "AU Cotality Home Prices (5 Capital City Aggregate)",
            "source": "Cotality Excel",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_date": cached_data.get("file_date") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "latest_excel_file": latest_file.name if latest_file else None,
        }


au_cotality_home_prices_service = AuCotalityHomePricesService()
