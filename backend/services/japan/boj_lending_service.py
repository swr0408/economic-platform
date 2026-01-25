"""
日銀貸出動向サービス（Bank of Japan Lending Trends）

データソース: 日本銀行 統計検索サイト
データコード: FAAPOBAL1（貸出動向・銀行計）
URL: https://www.stat-search.boj.or.jp/ssi/cgi-bin/famecgi2?cgi=$nme_a000&lstSelection=MD13

キャッシュ方式: Redis + ファイルフォールバック
更新: 毎月（月末から翌月初に公表）
スケジュール: 毎月1日から毎日9:30 JSTにチェック、更新したら以降スキップ

Selenium WebDriverを使用してBOJ統計検索サイトからデータを取得
"""
import json
import logging
import os
import time
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boj_lending_cache.json"


class BOJLendingService:
    """日銀貸出動向サービス"""

    # BOJ Statistical Search Site URLs
    BOJ_STAT_BASE_URL = "https://www.stat-search.boj.or.jp"
    BOJ_STAT_LENDING_URL = "https://www.stat-search.boj.or.jp/ssi/cgi-bin/famecgi2?cgi=$nme_a000&lstSelection=MD13"

    # Target data code
    DATA_CODE = "FAAPOBAL1"  # 貸出動向・銀行計

    DATA_CACHE_KEY = "japan:boj_lending:data"
    LAST_UPDATE_MONTH_KEY = "japan:boj_lending:last_update_month"

    def __init__(self):
        """Initialize BOJ Lending service"""
        pass

    def _get_chrome_driver(self, download_dir: str) -> webdriver.Chrome:
        """
        Create Chrome WebDriver with appropriate settings

        Args:
            download_dir: Directory for downloaded files

        Returns:
            Chrome WebDriver instance
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--lang=ja-JP")

        # Download settings
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Try to use chromedriver from PATH or common locations
        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.warning(f"Could not create Chrome driver with default settings: {e}")
            # Try with explicit service
            try:
                service = Service()
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e2:
                logger.error(f"Failed to create Chrome driver: {e2}")
                raise

        driver.implicitly_wait(10)
        return driver

    def _fetch_lending_data_selenium(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch BOJ Lending data using Selenium WebDriver
        Based on reference implementation from seasonality-app

        Returns:
            List of data points with date and value, or None if failed
        """
        import requests
        from io import StringIO
        import pandas as pd

        download_dir = tempfile.mkdtemp()
        driver = None
        original_window = None

        try:
            logger.info("Starting Selenium data fetch for BOJ Lending")
            driver = self._get_chrome_driver(download_dir)

            # Step 1: Navigate to BOJ Statistical Search Site - Lending page
            logger.info(f"Navigating to {self.BOJ_STAT_LENDING_URL}")
            driver.get(self.BOJ_STAT_LENDING_URL)

            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "searchCondition"))
            )
            logger.info("Page loaded successfully")

            original_window = driver.current_window_handle

            # Step 2: Click expand button to show all data series
            logger.info("Clicking expand button")
            try:
                expand_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        '//*[@id="menuSearchTabpanel"]/div[2]/div[1]/div[2]/input'
                    ))
                )
                expand_button.click()
            except Exception as e:
                logger.warning(f"Could not find expand button: {e}")

            # Wait for data list to appear
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "tableDataCode"))
            )
            logger.info("Data list loaded")

            # Step 3: Find and select FAAPOBAL1 checkbox
            logger.info(f"Looking for data code: {self.DATA_CODE}")

            # BOJ uses format "MD13'FAAPOBAL1" as the value
            full_code = f"MD13'{self.DATA_CODE}"
            logger.info(f"Full code to search: {full_code}")

            checkbox = None
            # Method 1: Try to find checkbox by value
            try:
                checkbox = driver.find_element(By.CSS_SELECTOR, f'input[value="{full_code}"]')
                logger.info(f"Found checkbox with value: {full_code}")
            except NoSuchElementException:
                logger.warning(f"Could not find checkbox with exact value: {full_code}")

            # Method 2: Try finding by ID
            if not checkbox:
                try:
                    checkbox = driver.find_element(By.ID, full_code)
                    logger.info(f"Found checkbox with ID: {full_code}")
                except NoSuchElementException:
                    pass

            # Method 3: Search all searchDataCode checkboxes
            if not checkbox:
                try:
                    checkboxes = driver.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"].searchDataCode')
                    logger.info(f"Found {len(checkboxes)} searchDataCode checkboxes")
                    for cb in checkboxes:
                        value = cb.get_attribute('value')
                        if value and self.DATA_CODE in value:
                            checkbox = cb
                            logger.info(f"Found checkbox with value containing {self.DATA_CODE}: {value}")
                            break
                except Exception as e:
                    logger.warning(f"Error searching checkboxes: {e}")

            if not checkbox:
                logger.error(f"Could not find checkbox for {self.DATA_CODE}")
                return None

            # Scroll to checkbox and click using JavaScript
            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
            driver.execute_script("arguments[0].click();", checkbox)
            logger.info(f"Selected {self.DATA_CODE}")

            # Step 4: Click "抽出条件に追加" (Add to extraction conditions) button
            logger.info("Adding to extraction conditions")
            add_button = None

            # Method 1: Find by onclick attribute
            try:
                add_button = driver.find_element(By.CSS_SELECTOR, 'a[onclick*="addAbstractCondition"]')
                logger.info("Found add button by onclick attribute")
            except NoSuchElementException:
                pass

            # Method 2: Find by link text
            if not add_button:
                try:
                    add_button = driver.find_element(By.LINK_TEXT, '抽出条件に追加')
                    logger.info("Found add button by link text")
                except NoSuchElementException:
                    pass

            # Method 3: Find by class
            if not add_button:
                try:
                    buttons = driver.find_elements(By.CSS_SELECTOR, 'a.largeButton')
                    for btn in buttons:
                        if '抽出条件に追加' in btn.text:
                            add_button = btn
                            logger.info("Found add button by searching largeButton elements")
                            break
                except Exception as e:
                    logger.warning(f"Error searching for add button: {e}")

            if not add_button:
                logger.error("Could not find '抽出条件に追加' button")
                return None

            driver.execute_script("arguments[0].click();", add_button)

            # Wait for result area
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "resultArea"))
            )
            logger.info("Added to extraction conditions")

            # Step 5: Set date range (from 2010)
            start_year = 2010
            logger.info(f"Setting date range from {start_year}")
            try:
                from_year = driver.find_element(By.ID, "fromYear")
                from_year.clear()
                from_year.send_keys(str(start_year))
                logger.info(f"Set start year to {start_year}")
            except NoSuchElementException:
                logger.warning("Could not find fromYear field")

            # Step 6: Click extraction button (opens new window)
            logger.info("Clicking extraction button")
            extract_button = None

            try:
                extract_button = driver.find_element(By.CSS_SELECTOR, 'a[onclick*="submit_code_main"]')
                logger.info("Found extraction button by onclick")
            except NoSuchElementException:
                pass

            if not extract_button:
                try:
                    links = driver.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        if '抽出' in link.text:
                            class_attr = link.get_attribute('class') or ''
                            if 'middleButton' in class_attr:
                                extract_button = link
                                logger.info("Found extraction button by text and class")
                                break
                except Exception as e:
                    logger.warning(f"Error finding extraction button: {e}")

            if not extract_button:
                logger.error("Could not find '抽出' button")
                return None

            driver.execute_script("arguments[0].click();", extract_button)

            # Wait for new window to open
            WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)

            # Switch to new window
            for window_handle in driver.window_handles:
                if window_handle != original_window:
                    driver.switch_to.window(window_handle)
                    break

            logger.info("Switched to extraction window")
            download_window = driver.current_window_handle

            # Step 7: Click download button (opens another window)
            logger.info("Looking for download button")
            download_button = None

            try:
                download_button = driver.find_element(By.CSS_SELECTOR, 'a[onclick*="DLform_MM.submit"]')
                logger.info("Found download button")
            except NoSuchElementException:
                pass

            if not download_button:
                try:
                    download_button = driver.find_element(By.PARTIAL_LINK_TEXT, "ダウンロード")
                    logger.info("Found download button by text")
                except NoSuchElementException:
                    logger.error("Could not find download button")
                    return None

            driver.execute_script("arguments[0].click();", download_button)
            logger.info("Clicked download button")

            # Wait for third window to open
            time.sleep(2)

            all_windows = driver.window_handles
            logger.info(f"Total windows after download click: {len(all_windows)}")

            if len(all_windows) > 2:
                # Switch to the newest window
                for window_handle in all_windows:
                    if window_handle not in [original_window, download_window]:
                        driver.switch_to.window(window_handle)
                        logger.info("Switched to download link window")
                        logger.info(f"Download window URL: {driver.current_url}")
                        break

                # Step 8: Get CSV download link
                csv_url = None
                try:
                    csv_links = driver.find_elements(By.PARTIAL_LINK_TEXT, "CSV")
                    logger.info(f"Found {len(csv_links)} CSV links")

                    if csv_links:
                        csv_url = csv_links[0].get_attribute('href')
                        logger.info(f"CSV download URL: {csv_url}")
                    else:
                        links = driver.find_elements(By.TAG_NAME, "a")
                        for link in links:
                            href = link.get_attribute('href')
                            if href and ('download' in href.lower() or 'dl' in href.lower()):
                                csv_url = href
                                logger.info(f"Found download link: {href}")
                                break
                except Exception as e:
                    logger.error(f"Error finding CSV link: {e}")

                if not csv_url:
                    logger.error("Could not find CSV download URL")
                    return None

                # Step 9: Download CSV using requests
                logger.info(f"Downloading CSV from: {csv_url}")
                response = requests.get(csv_url, timeout=30)
                response.encoding = 'shift_jis'

                # Parse CSV
                df = pd.read_csv(StringIO(response.text))
                logger.info(f"Downloaded CSV with {len(df)} rows, {len(df.columns)} columns")

                # Process the data
                return self._process_dataframe(df)

            else:
                logger.error(f"Third window did not open. Total windows: {len(all_windows)}")
                return None

        except TimeoutException as e:
            logger.error(f"Timeout during Selenium operation: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching BOJ Lending data: {e}", exc_info=True)
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                    logger.info("WebDriver closed")
                except Exception as e:
                    logger.warning(f"Error closing driver: {e}")

            # Cleanup download directory
            try:
                import shutil
                shutil.rmtree(download_dir, ignore_errors=True)
            except Exception:
                pass

    def _process_dataframe(self, df) -> Optional[List[Dict[str, Any]]]:
        """
        Process DataFrame from BOJ CSV into standardized format

        Args:
            df: pandas DataFrame from BOJ CSV

        Returns:
            List of data points with date and value
        """
        import pandas as pd

        series_data = []

        try:
            # Find the row where actual data starts (first row with date-like value)
            data_start_row = 0
            for i, row in df.iterrows():
                first_val = str(row.iloc[0]).strip()
                if first_val.replace('/', '').replace('-', '').isdigit():
                    data_start_row = i
                    break

            logger.info(f"Data starts at row {data_start_row}")

            # Extract data from data_start_row onwards
            for i in range(data_start_row, len(df)):
                row = df.iloc[i]

                # Parse date (format might be YYYY/MM or YYYY-MM)
                date_str = str(row.iloc[0]).strip()
                if not date_str or date_str == 'nan':
                    continue

                try:
                    if '/' in date_str:
                        parts = date_str.split('/')
                        if len(parts) >= 2:
                            year = parts[0]
                            month = parts[1].zfill(2)
                            formatted_date = f"{year}-{month}"
                        else:
                            continue
                    elif '-' in date_str:
                        parts = date_str.split('-')
                        if len(parts) >= 2:
                            year = parts[0]
                            month = parts[1].zfill(2)
                            formatted_date = f"{year}-{month}"
                        else:
                            continue
                    else:
                        continue

                    # Get value (second column)
                    value = row.iloc[1] if len(row) > 1 else None
                    if pd.isna(value):
                        continue

                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        continue

                    series_data.append({
                        "date": formatted_date,
                        "value": round(value, 1)
                    })

                except Exception as e:
                    logger.debug(f"Error parsing row {i}: {e}")
                    continue

            # Sort by date
            series_data.sort(key=lambda x: x["date"])

            # Filter to data from 2000 onwards
            if series_data:
                cutoff_date = "2000-01"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            logger.info(f"Processed {len(series_data)} data points")
            return series_data

        except Exception as e:
            logger.error(f"Error processing DataFrame: {e}", exc_info=True)
            return None

    def _parse_csv_file(self, csv_path: Path) -> Optional[List[Dict[str, Any]]]:
        """
        Parse downloaded CSV file from BOJ

        Args:
            csv_path: Path to CSV file

        Returns:
            List of data points
        """
        try:
            import pandas as pd

            # Try different encodings
            for encoding in ['shift_jis', 'cp932', 'utf-8', 'utf-8-sig']:
                try:
                    # BOJ CSV files typically have header rows to skip
                    df = pd.read_csv(csv_path, encoding=encoding, skiprows=1)
                    break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            else:
                logger.error(f"Could not read CSV with any encoding: {csv_path}")
                return None

            logger.info(f"CSV shape: {df.shape}")
            logger.info(f"CSV columns: {df.columns.tolist()}")

            series_data = []

            # Parse data rows
            for idx, row in df.iterrows():
                try:
                    # First column is typically date
                    date_val = row.iloc[0]
                    if pd.isna(date_val):
                        continue

                    # Parse date (format: YYYY/MM or YYYYMM)
                    date_str = str(date_val).strip()

                    if '/' in date_str:
                        parts = date_str.split('/')
                        if len(parts) >= 2:
                            year = parts[0]
                            month = parts[1].zfill(2)
                            formatted_date = f"{year}-{month}"
                    elif len(date_str) == 6:
                        # YYYYMM format
                        year = date_str[:4]
                        month = date_str[4:6]
                        formatted_date = f"{year}-{month}"
                    else:
                        continue

                    # Get value (second column)
                    value = row.iloc[1]
                    if pd.isna(value):
                        continue

                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        continue

                    series_data.append({
                        "date": formatted_date,
                        "value": round(value, 1)  # Unit: 100 million yen (億円)
                    })

                except Exception as e:
                    logger.debug(f"Error parsing row {idx}: {e}")
                    continue

            # Sort by date
            series_data.sort(key=lambda x: x["date"])

            # Filter to data from 2000 onwards
            if series_data:
                cutoff_date = "2000-01"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            logger.info(f"Parsed {len(series_data)} data points from CSV")
            return series_data

        except Exception as e:
            logger.error(f"Error parsing CSV file: {e}", exc_info=True)
            return None

    def get_boj_lending_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get BOJ Lending data with caching

        Args:
            force_refresh: Force refresh from source

        Returns:
            BOJ Lending data dictionary
        """
        # Redis cache check
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

        # Fetch from BOJ
        fetched_data = self._fetch_lending_data_selenium()
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

        # File cache fallback
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

    def _calculate_yoy(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate Year-over-Year change from raw lending data

        Args:
            raw_data: List of data points with date and value

        Returns:
            List of data points with YoY percentage change
        """
        if not raw_data:
            return []

        # Create a map of date -> value
        value_map = {item["date"]: item["value"] for item in raw_data}

        yoy_data = []
        for item in raw_data:
            date_str = item["date"]
            value = item["value"]

            # Parse date and get previous year's date
            try:
                year, month = date_str.split("-")
                prev_year = str(int(year) - 1)
                prev_date = f"{prev_year}-{month}"

                prev_value = value_map.get(prev_date)
                if prev_value is not None and prev_value != 0:
                    yoy_change = ((value - prev_value) / prev_value) * 100
                    yoy_data.append({
                        "date": date_str,
                        "value": round(yoy_change, 2)
                    })
            except (ValueError, AttributeError):
                continue

        return yoy_data

    def get_boj_lending_yoy_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get BOJ Lending YoY data with caching

        Args:
            force_refresh: Force refresh from source

        Returns:
            BOJ Lending YoY data dictionary (percentage)
        """
        # First get raw data
        raw_result = self.get_boj_lending_data(force_refresh=force_refresh)

        if raw_result.get("error"):
            return raw_result

        raw_data = raw_result.get("data", [])
        yoy_data = self._calculate_yoy(raw_data)

        return {
            "data": yoy_data,
            "latest": yoy_data[-1] if yoy_data else None,
            "cached": raw_result.get("cached", False),
            "source": raw_result.get("source", "unknown"),
            "last_updated": raw_result.get("last_updated")
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
            "indicator": "BOJ Lending Trends",
            "source": "Bank of Japan Statistical Search",
            "data_code": self.DATA_CODE,
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
        毎月1日から毎日チェック、更新したらその月は以降スキップ

        Returns:
            更新結果
        """
        now = datetime.now(JST)
        current_month_str = now.strftime("%Y-%m")

        # 今月既に更新済みかチェック
        last_update_month = redis_client.get(self.LAST_UPDATE_MONTH_KEY)
        if last_update_month == current_month_str:
            logger.info(f"BOJ Lending: Already updated this month ({current_month_str}), skipping")
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
        logger.info("BOJ Lending: Checking for updates...")
        result = self.get_boj_lending_data(force_refresh=True)

        # 新しいデータの最新日付を確認
        new_latest_date = result.get("latest", {}).get("date") if result.get("latest") else None

        # データが更新されたかチェック
        if new_latest_date and new_latest_date != old_latest_date:
            # 更新があった場合、今月を記録
            redis_client.set(self.LAST_UPDATE_MONTH_KEY, current_month_str, expire=0)
            logger.info(f"BOJ Lending: Data updated! {old_latest_date} -> {new_latest_date}")
            return {
                "status": "updated",
                "old_latest_date": old_latest_date,
                "new_latest_date": new_latest_date,
                "update_month": current_month_str
            }
        elif new_latest_date:
            logger.info(f"BOJ Lending: No new data (latest: {new_latest_date})")
            return {
                "status": "no_change",
                "latest_date": new_latest_date
            }
        else:
            logger.warning("BOJ Lending: Failed to fetch data")
            return {
                "status": "error",
                "reason": "Failed to fetch data"
            }


# Singleton instance
boj_lending_service = BOJLendingService()
