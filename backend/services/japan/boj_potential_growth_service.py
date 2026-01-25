"""
日銀潜在成長率サービス（Bank of Japan）

データソース: 日本銀行（Bank of Japan）
URL: https://www.boj.or.jp/research/research_data/gap/gap.xlsx

キャッシュ方式: Redis + ファイルフォールバック
更新: 四半期毎（1月、4月、7月、10月の7日頃）
スケジュール: 該当月は毎日チェック、更新したら以降スキップ
"""
import json
import logging
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boj_potential_growth_cache.json"
TEMP_DIR = CACHE_DIR / "temp"


class BOJPotentialGrowthService:
    """日銀潜在成長率サービス"""

    # BOJ GDP Gap Data URL
    BOJ_GDP_GAP_URL = "https://www.boj.or.jp/research/research_data/gap/gap.xlsx"

    DATA_CACHE_KEY = "japan:boj_potential_growth:data"
    LAST_UPDATE_MONTH_KEY = "japan:boj_potential_growth:last_update_month"

    # 更新対象月（1月、4月、7月、10月）
    UPDATE_MONTHS = [1, 4, 7, 10]

    def __init__(self):
        """Initialize BOJ Potential Growth service"""
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def _download_excel_file(self) -> Optional[Path]:
        """
        Download BOJ GDP Gap Excel file

        Returns:
            Path to downloaded Excel file, or None if failed
        """
        try:
            logger.info(f"Downloading BOJ GDP Gap data from {self.BOJ_GDP_GAP_URL}")

            response = requests.get(self.BOJ_GDP_GAP_URL, timeout=60)
            response.raise_for_status()

            # Save Excel file
            excel_path = TEMP_DIR / "boj_gdp_gap.xlsx"
            excel_path.write_bytes(response.content)

            logger.info(f"Downloaded {len(response.content)} bytes")
            return excel_path

        except Exception as e:
            logger.error(f"Error downloading BOJ GDP Gap data: {e}")
            return None

    def _parse_potential_growth_excel(self, excel_path: Path) -> Optional[List[Dict[str, Any]]]:
        """
        Parse BOJ Potential Growth Rate from Excel file

        Excel format:
        - Column 0: Date in format "YYYY.XQ" (e.g., "1983.1Q")
        - Column 7 (H): Date for potential growth section
        - Column 8 (I): Potential growth rate (y/y % chg.)

        Args:
            excel_path: Path to Excel file

        Returns:
            List of data points with date and value
        """
        try:
            logger.info(f"Parsing BOJ Potential Growth Rate from Excel: {excel_path}")

            # Read Excel file - skiprows=4 to get to the data rows
            df = pd.read_excel(excel_path, sheet_name=0, skiprows=4)

            logger.info(f"Excel shape: {df.shape}")
            logger.info(f"Excel columns: {df.columns.tolist()}")

            # Column 7 (H) has dates for potential growth, Column 8 (I) has values
            date_col = df.columns[7]
            potential_growth_col = df.columns[8]

            logger.info(f"Date column (H): {date_col}")
            logger.info(f"Potential growth column (I): {potential_growth_col}")

            # Extract data points
            series_data = []

            for idx, row in df.iterrows():
                try:
                    # Get date from column 7 (H)
                    date_val = row[date_col]
                    if pd.isna(date_val):
                        continue

                    # Parse date format "2023.1 : 2023.2Q-2023.3Q" or "2025.1 : 2025.2Q"
                    date_str = str(date_val).strip()

                    # Extract the last part after colon which contains the actual quarter
                    # Format: "YYYY.X : YYYY.XQ" or "YYYY.X : YYYY.XQ-YYYY.XQ"
                    if ':' in date_str:
                        # Get the part after colon
                        after_colon = date_str.split(':')[1].strip()

                        # If there's a range (e.g., "2023.2Q-2023.3Q"), take the last part
                        if '-' in after_colon:
                            quarter_part = after_colon.split('-')[-1].strip()
                        else:
                            quarter_part = after_colon

                        # Parse "2023.2Q" to "2023-Q2"
                        if '.' in quarter_part and 'Q' in quarter_part:
                            parts = quarter_part.split('.')
                            if len(parts) == 2:
                                year = parts[0]
                                quarter = parts[1].replace('Q', '')  # "2Q" -> "2"
                                date_str = f"{year}-Q{quarter}"
                            else:
                                logger.debug(f"Could not parse quarter part: {quarter_part}")
                                continue
                        else:
                            logger.debug(f"Quarter part format unexpected: {quarter_part}")
                            continue
                    else:
                        logger.debug(f"Date format does not contain colon: {date_val}")
                        continue

                    # Get potential growth rate value
                    potential_growth_value = row[potential_growth_col]

                    # Skip if value is NaN or invalid
                    if pd.isna(potential_growth_value):
                        continue

                    # Convert to float
                    if isinstance(potential_growth_value, str):
                        potential_growth_value = potential_growth_value.strip()
                        if not potential_growth_value or potential_growth_value == '-':
                            continue
                        potential_growth_value = float(potential_growth_value)
                    else:
                        potential_growth_value = float(potential_growth_value)

                    series_data.append({
                        "date": date_str,
                        "value": round(potential_growth_value, 2)
                    })

                except Exception as e:
                    logger.debug(f"Error processing row {idx}: {e}")
                    continue

            # Sort by date
            series_data.sort(key=lambda x: (int(x["date"][:4]), int(x["date"][-1])))

            # Filter to data from 2000 onwards
            if series_data:
                cutoff_date = "2000-Q1"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            logger.info(f"Processed BOJ Potential Growth Rate data: {len(series_data)} data points")
            return series_data

        except Exception as e:
            logger.error(f"Error parsing BOJ Potential Growth Rate Excel: {e}", exc_info=True)
            return None

    def _fetch_potential_growth_data(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch BOJ Potential Growth Rate data from BOJ Excel file

        Returns:
            List of data points
        """
        try:
            # Download Excel file
            excel_path = self._download_excel_file()
            if not excel_path:
                return None

            # Parse Excel
            series_data = self._parse_potential_growth_excel(excel_path)

            # Clean up temp files
            try:
                for file in TEMP_DIR.glob("*"):
                    if file.is_file():
                        file.unlink()
            except Exception as e:
                logger.warning(f"Error cleaning up temp files: {e}")

            return series_data

        except Exception as e:
            logger.error(f"Error fetching BOJ Potential Growth Rate data: {e}")
            return None

    def get_boj_potential_growth_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get BOJ Potential GDP Growth Rate data with caching

        Args:
            force_refresh: Force refresh from source

        Returns:
            BOJ Potential Growth Rate data dictionary
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                data = cached_data.get("data", [])
                return {
                    "data": data,
                    "latest": data[-1] if data else None,
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # BOJからデータ取得
        fetched_data = self._fetch_potential_growth_data()
        if fetched_data:
            cache_payload = {
                "data": fetched_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": fetched_data,
                "latest": fetched_data[-1] if fetched_data else None,
                "cached": False,
                "source": "boj",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            data = file_cache.get("data", [])
            return {
                "data": data,
                "latest": data[-1] if data else None,
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

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """Load from file cache"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """Save to file cache"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """Invalidate Redis cache"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        last_update_month = redis_client.get(self.LAST_UPDATE_MONTH_KEY)

        return {
            "indicator": "BOJ Potential GDP Growth Rate",
            "source": "Bank of Japan",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "last_update_month": last_update_month,
            "update_months": self.UPDATE_MONTHS
        }

    def scheduled_update(self) -> Dict[str, Any]:
        """
        スケジューラーから呼び出される更新メソッド
        1月、4月、7月、10月のみチェックし、更新したらその月は以降スキップ

        Returns:
            更新結果
        """
        now = datetime.now(JST)
        current_month = now.month
        current_month_str = now.strftime("%Y-%m")

        # 更新対象月かチェック
        if current_month not in self.UPDATE_MONTHS:
            logger.info(f"BOJ Potential Growth Rate: Not an update month ({current_month}), skipping")
            return {
                "status": "skipped",
                "reason": f"Not an update month (current: {current_month}, update months: {self.UPDATE_MONTHS})"
            }

        # 今月既に更新済みかチェック
        last_update_month = redis_client.get(self.LAST_UPDATE_MONTH_KEY)
        if last_update_month == current_month_str:
            logger.info(f"BOJ Potential Growth Rate: Already updated this month ({current_month_str}), skipping")
            return {
                "status": "skipped",
                "reason": f"Already updated this month ({current_month_str})",
                "last_update_month": last_update_month
            }

        # 現在のデータの最新日付を取得
        cached_data = redis_client.get(self.DATA_CACHE_KEY)
        old_latest_date = None
        if cached_data and cached_data.get("data"):
            old_latest_date = cached_data["data"][-1].get("date")

        # データを取得（強制更新）
        logger.info(f"BOJ Potential Growth Rate: Checking for updates...")
        result = self.get_boj_potential_growth_data(force_refresh=True)

        # 新しいデータの最新日付を確認
        new_latest_date = result.get("latest", {}).get("date") if result.get("latest") else None

        # データが更新されたかチェック
        if new_latest_date and new_latest_date != old_latest_date:
            # 更新があった場合、今月を記録
            redis_client.set(self.LAST_UPDATE_MONTH_KEY, current_month_str, expire=0)
            logger.info(f"BOJ Potential Growth Rate: Data updated! {old_latest_date} -> {new_latest_date}")
            return {
                "status": "updated",
                "old_latest_date": old_latest_date,
                "new_latest_date": new_latest_date,
                "update_month": current_month_str
            }
        elif new_latest_date:
            logger.info(f"BOJ Potential Growth Rate: No new data (latest: {new_latest_date})")
            return {
                "status": "no_change",
                "latest_date": new_latest_date
            }
        else:
            logger.warning("BOJ Potential Growth Rate: Failed to fetch data")
            return {
                "status": "error",
                "reason": "Failed to fetch data"
            }


# Singleton instance
boj_potential_growth_service = BOJPotentialGrowthService()
