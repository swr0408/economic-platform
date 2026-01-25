"""
潜在成長率サービス（内閣府）

データソース: 内閣府（Cabinet Office）
URL: https://www5.cao.go.jp/keizai3/getsurei/getsurei-index.html から自動検出

キャッシュ方式: Redis + ファイルフォールバック
更新: 不定期（月例経済報告の付属資料として公表）
スケジュール: 毎日チェック、更新した月は以降スキップ
"""
import json
import logging
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "potential_growth_cache.json"
TEMP_DIR = CACHE_DIR / "temp"


class PotentialGrowthService:
    """潜在成長率サービス"""

    # Cabinet Office GDP Gap Data - 一覧ページからURLを自動検出
    INDEX_PAGE_URL = "https://www5.cao.go.jp/keizai3/getsurei/getsurei-index.html"
    BASE_URL = "https://www5.cao.go.jp/keizai3/getsurei/"

    DATA_CACHE_KEY = "japan:potential_growth:data"
    LAST_UPDATE_MONTH_KEY = "japan:potential_growth:last_update_month"

    def __init__(self):
        """Initialize Potential Growth service"""
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def _detect_excel_url(self) -> Optional[str]:
        """
        一覧ページからGDPギャップExcelファイルのURLを自動検出

        Returns:
            Excel file URL, or None if not found
        """
        try:
            logger.info(f"Fetching index page: {self.INDEX_PAGE_URL}")
            response = requests.get(self.INDEX_PAGE_URL, timeout=30)
            response.raise_for_status()

            # エンコーディング検出
            response.encoding = response.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')

            # GDPギャップのリンクを探す（gap.xlsxパターン）
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                link_text = link.get_text(strip=True)

                # gap.xlsxを含むリンクを探す
                if re.search(r'\d+gap\.xlsx?$', href, re.IGNORECASE):
                    # 相対URLを絶対URLに変換
                    if href.startswith('http'):
                        excel_url = href
                    else:
                        excel_url = self.BASE_URL + href.lstrip('./')

                    logger.info(f"Detected GDP Gap Excel URL: {excel_url}")
                    return excel_url

            logger.error("Could not find GDP Gap Excel link on index page")
            return None

        except Exception as e:
            logger.error(f"Error detecting Excel URL: {e}")
            return None

    def _download_excel_file(self) -> Optional[Path]:
        """
        Download GDP Gap Excel file from Cabinet Office
        URLは一覧ページから自動検出

        Returns:
            Path to downloaded Excel file, or None if failed
        """
        try:
            # URLを自動検出
            excel_url = self._detect_excel_url()
            if not excel_url:
                logger.error("Could not detect Excel URL")
                return None

            logger.info(f"Downloading GDP Gap data from {excel_url}")

            response = requests.get(excel_url, timeout=60)
            response.raise_for_status()

            # Save Excel file
            excel_path = TEMP_DIR / "gdp_gap.xlsx"
            excel_path.write_bytes(response.content)

            logger.info(f"Downloaded {len(response.content)} bytes")
            return excel_path

        except Exception as e:
            logger.error(f"Error downloading GDP Gap data: {e}")
            return None

    def _parse_potential_growth_excel(self, excel_path: Path) -> Optional[List[Dict[str, Any]]]:
        """
        Parse Potential GDP Growth Rate from Excel file

        Args:
            excel_path: Path to Excel file

        Returns:
            List of data points with date and value
        """
        try:
            logger.info(f"Parsing Potential GDP Growth Rate from Excel: {excel_path}")

            # Read Excel file - skiprows=5 to get to the header row
            df = pd.read_excel(excel_path, sheet_name=0, skiprows=5)

            logger.info(f"Excel shape: {df.shape}")
            logger.info(f"Excel columns: {df.columns.tolist()}")

            # Find Potential GDP Growth Rate column
            potential_growth_col = None
            for col in df.columns:
                col_str = str(col)
                if 'Potential GDP Growth Rate' in col_str or 'Potential Growth Rate' in col_str:
                    potential_growth_col = col
                    break

            if potential_growth_col is None:
                logger.error("Potential GDP Growth Rate column not found")
                return None

            logger.info(f"Found Potential Growth Rate column: {potential_growth_col}")

            # Extract data points
            series_data = []
            current_year = None

            # Quarter mapping - Unicode Roman numerals used in the Excel file
            quarter_map = {
                '\u2160': 'Q1',  # Ⅰ
                '\u2161': 'Q2',  # Ⅱ
                '\u2162': 'Q3',  # Ⅲ
                '\u2163': 'Q4',  # Ⅳ
                'Ⅰ': 'Q1',
                'Ⅱ': 'Q2',
                'Ⅲ': 'Q3',
                'Ⅳ': 'Q4',
                'I': 'Q1',
                'II': 'Q2',
                'III': 'Q3',
                'IV': 'Q4',
                '1': 'Q1',
                '2': 'Q2',
                '3': 'Q3',
                '4': 'Q4',
            }

            for idx, row in df.iterrows():
                try:
                    # Get year from first column
                    year_val = row.iloc[0]
                    if pd.notna(year_val) and isinstance(year_val, (int, float)):
                        current_year = int(year_val)

                    # Get quarter from second column
                    quarter_val = row.iloc[1]
                    if pd.isna(quarter_val) or current_year is None:
                        continue

                    # Map quarter to Q1, Q2, Q3, Q4
                    quarter_str = str(quarter_val).strip()
                    quarter = quarter_map.get(quarter_str)

                    if not quarter:
                        # Try to extract Roman numerals or quarter number
                        quarter_upper = quarter_str.upper()
                        if quarter_str == 'I' or 'I' == quarter_upper.strip() or quarter_str.endswith('I'):
                            quarter = 'Q1'
                        elif quarter_str == 'II' or 'II' in quarter_upper or quarter_str.endswith('II'):
                            quarter = 'Q2'
                        elif quarter_str == 'III' or 'III' in quarter_upper or quarter_str.endswith('III'):
                            quarter = 'Q3'
                        elif quarter_str == 'IV' or 'IV' in quarter_upper or quarter_str.endswith('IV'):
                            quarter = 'Q4'
                        else:
                            logger.debug(f"Could not parse quarter: '{quarter_str}'")
                            continue

                    # Get Potential Growth Rate value
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

                    # Create date string in YYYY-QX format
                    date_str = f"{current_year}-{quarter}"

                    series_data.append({
                        "date": date_str,
                        "value": round(potential_growth_value, 2)
                    })

                except Exception as e:
                    logger.debug(f"Error processing row {idx}: {e}")
                    continue

            # Sort by date
            series_data.sort(key=lambda x: (int(x["date"][:4]), x["date"][5:]))

            # Filter to data from 2000 onwards
            if series_data:
                cutoff_date = "2000-Q1"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            logger.info(f"Processed Potential Growth Rate data: {len(series_data)} data points")
            return series_data

        except Exception as e:
            logger.error(f"Error parsing Potential Growth Rate Excel: {e}", exc_info=True)
            return None

    def _fetch_potential_growth_data(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch Potential GDP Growth Rate data from Cabinet Office Excel file

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
            logger.error(f"Error fetching Potential Growth Rate data: {e}")
            return None

    def get_potential_growth_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get Potential GDP Growth Rate data with caching

        Args:
            force_refresh: Force refresh from source

        Returns:
            Potential Growth Rate data dictionary
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

        # Cabinet Officeからデータ取得
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
                "source": "cabinet_office",
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
            "indicator": "Potential GDP Growth Rate",
            "source": "Cabinet Office",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "last_update_month": last_update_month
        }

    def scheduled_update(self) -> Dict[str, Any]:
        """
        スケジューラーから呼び出される更新メソッド
        更新した月は以降スキップする

        Returns:
            更新結果
        """
        now = datetime.now(JST)
        current_month = now.strftime("%Y-%m")

        # 今月既に更新済みかチェック
        last_update_month = redis_client.get(self.LAST_UPDATE_MONTH_KEY)
        if last_update_month == current_month:
            logger.info(f"Potential Growth Rate: Already updated this month ({current_month}), skipping")
            return {
                "status": "skipped",
                "reason": f"Already updated this month ({current_month})",
                "last_update_month": last_update_month
            }

        # 現在のデータの最新日付を取得
        cached_data = redis_client.get(self.DATA_CACHE_KEY)
        old_latest_date = None
        if cached_data and cached_data.get("data"):
            old_latest_date = cached_data["data"][-1].get("date")

        # データを取得（強制更新）
        logger.info(f"Potential Growth Rate: Checking for updates...")
        result = self.get_potential_growth_data(force_refresh=True)

        # 新しいデータの最新日付を確認
        new_latest_date = result.get("latest", {}).get("date") if result.get("latest") else None

        # データが更新されたかチェック
        if new_latest_date and new_latest_date != old_latest_date:
            # 更新があった場合、今月を記録
            redis_client.set(self.LAST_UPDATE_MONTH_KEY, current_month, expire=0)
            logger.info(f"Potential Growth Rate: Data updated! {old_latest_date} -> {new_latest_date}")
            return {
                "status": "updated",
                "old_latest_date": old_latest_date,
                "new_latest_date": new_latest_date,
                "update_month": current_month
            }
        elif new_latest_date:
            logger.info(f"Potential Growth Rate: No new data (latest: {new_latest_date})")
            return {
                "status": "no_change",
                "latest_date": new_latest_date
            }
        else:
            logger.warning("Potential Growth Rate: Failed to fetch data")
            return {
                "status": "error",
                "reason": "Failed to fetch data"
            }


# Singleton instance
potential_growth_service = PotentialGrowthService()
