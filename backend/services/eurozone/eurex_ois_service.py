"""
Eurex Three-Month Euro STR Futures OIS Service
Fetches D. Settle values from Eurex website and calculates OIS curve

Data includes:
- Contract month and D. Settle values
- Implied rate calculation (100 - D. Settle)

Publication schedule: Daily 20:00-20:10 CET (winter time: 21:00-21:10 CET)
Update check: Every 10 minutes during 20:00-21:10 JST

データソース:
- Eurex (Three-Month Euro STR Futures)
- URL: https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eurex_ois_cache.json"
HISTORY_CACHE_FILE = CACHE_DIR / "eurex_ois_history.json"


class EurexOISService:
    """Service for fetching Eurex Three-Month Euro STR Futures data"""

    # Eurex website URL
    EUREX_URL = "https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480"

    DATA_CACHE_KEY = "monetary_policy:eurex_ois:data"
    HISTORY_CACHE_KEY = "monetary_policy:eurex_ois:history"

    def __init__(self):
        pass

    def _is_dst(self, dt: datetime) -> bool:
        """
        Check if a date is in Daylight Saving Time (summer time in Europe)
        Europe DST: Last Sunday of March to last Sunday of October
        """
        # Get last Sunday of March
        march_last = datetime(dt.year, 3, 31)
        while march_last.weekday() != 6:  # 6 = Sunday
            march_last -= timedelta(days=1)

        # Get last Sunday of October
        october_last = datetime(dt.year, 10, 31)
        while october_last.weekday() != 6:
            october_last -= timedelta(days=1)

        return march_last <= dt < october_last

    def is_update_time(self) -> bool:
        """
        Check if current time is within the Eurex update window:
        Daily 20:00-20:10 CET (winter time: 21:00-21:10 CET) = 20:00-20:10 / 21:00-21:10 JST
        """
        now = datetime.now(JST)

        # Skip weekends
        if now.weekday() >= 5:
            return False

        # Determine if we're in DST (summer time)
        is_summer_time = self._is_dst(now)

        # JST times:
        # Winter (CET): 21:00-21:10 JST
        # Summer (CEST): 20:00-20:10 JST
        if is_summer_time:
            start_hour, start_min = 20, 0
            end_hour, end_min = 20, 10
        else:
            start_hour, start_min = 21, 0
            end_hour, end_min = 21, 10

        current_time = now.time()
        start_time = datetime.strptime(f"{start_hour:02d}:{start_min:02d}", "%H:%M").time()
        end_time = datetime.strptime(f"{end_hour:02d}:{end_min:02d}", "%H:%M").time()

        return start_time <= current_time <= end_time

    def _fetch_eurex_data(self) -> Optional[List[Dict]]:
        """
        Fetch Eurex STR Futures data using Selenium
        """
        driver = None
        try:
            # Chrome options
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            print(f"Fetching Eurex data from {self.EUREX_URL}")

            # Initialize Chrome driver
            # Docker環境では/usr/bin/chromiumを使用
            import os
            if os.path.exists('/usr/bin/chromium'):
                chrome_options.binary_location = '/usr/bin/chromium'
                # chromiumdriverの代わりにwebdriver-managerで自動取得
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.os_manager import ChromeType
                service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
            else:
                service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

            # Navigate to page
            driver.get(self.EUREX_URL)

            # Wait for React table to load
            wait = WebDriverWait(driver, 45)

            # Wait for react-table
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "react-table")))
                print("React table found")
            except Exception as e:
                print(f"React table not found: {e}")

            # Additional wait for dynamic content
            time.sleep(15)

            # Try to find the table
            table_found = False
            data_rows = []

            # Strategy 1: Find overflow container
            try:
                overflow_containers = driver.find_elements(
                    By.CSS_SELECTOR,
                    "div.overflow-x-auto.scrollbar-d-none.position-relative.d-flex.flex-grow-1"
                )

                if len(overflow_containers) >= 1:
                    print(f"Found {len(overflow_containers)} overflow containers")
                    first_container = overflow_containers[0]
                    react_table = first_container.find_element(By.CSS_SELECTOR, ".flex-grow-1 .react-table")

                    if react_table:
                        tbody = react_table.find_element(By.TAG_NAME, "tbody")
                        data_rows = tbody.find_elements(By.TAG_NAME, "tr")
                        table_found = True
                        print(f"Found {len(data_rows)} data rows")
            except Exception as e:
                print(f"Strategy 1 failed: {e}")

            # Strategy 2: Find any react-table
            if not table_found:
                try:
                    react_tables = driver.find_elements(By.CLASS_NAME, "react-table")
                    for idx, table in enumerate(react_tables):
                        try:
                            tbody = table.find_element(By.TAG_NAME, "tbody")
                            rows = tbody.find_elements(By.TAG_NAME, "tr")
                            if len(rows) > 1:
                                thead = table.find_element(By.TAG_NAME, "thead")
                                header_text = thead.text
                                if 'Settle' in header_text or 'SETTLE' in header_text.upper():
                                    data_rows = rows
                                    table_found = True
                                    break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"Strategy 2 failed: {e}")

            if not table_found or not data_rows:
                print("Could not find settlement data table")
                return None

            # Parse table data
            # テーブル構造（2025年1月時点）:
            # [0] Contract Type, [1] Contract Date, [2] Open, [3] High, [4] Low,
            # [5] Last, [6] D. Settle, [7] Volume, [8] OI adj
            result = []
            contract_date_col = 1
            settle_col = 6

            for row in data_rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if not cells:
                    continue

                cell_texts = []
                for cell in cells:
                    text = cell.get_attribute('textContent')
                    if not text:
                        text = cell.text
                    cell_texts.append(text.strip() if text else '')

                if len(cell_texts) <= max(contract_date_col, settle_col):
                    continue

                contract_date_str = cell_texts[contract_date_col]
                settle_value_str = cell_texts[settle_col]

                try:
                    if not contract_date_str or not settle_value_str:
                        continue

                    settle_value = float(settle_value_str.replace(',', '').replace(' ', ''))

                    if settle_value == 0.0:
                        continue

                    implied_rate = round(100 - settle_value, 4)

                    if '/' in contract_date_str:
                        parts = contract_date_str.split('/')
                        if len(parts) == 3:
                            day, month, year = parts
                            date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

                            month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                                           'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
                            month_idx = int(month) - 1
                            if 0 <= month_idx < 12:
                                month_abbr = month_names[month_idx]
                                year_short = year[-2:] if len(year) >= 2 else year
                                contract_label = f"{month_abbr} {year_short}"

                                result.append({
                                    'date': contract_date_str,
                                    'sort_date': date_str,
                                    'contract': contract_label,
                                    'settle': settle_value,
                                    'implied_rate': implied_rate
                                })

                except (ValueError, IndexError) as e:
                    continue

            print(f"Fetched {len(result)} Eurex OIS data points")

            # Sort by date and limit to 12 months
            if result:
                result.sort(key=lambda x: x['sort_date'])
                result = result[:12]

            return result

        except Exception as e:
            print(f"Error fetching Eurex data: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            if driver:
                driver.quit()

    def _save_daily_snapshot(self, data: Dict) -> None:
        """Save daily snapshot to history (keeps last 30 days)"""
        try:
            # Load existing history from Redis or file
            history = redis_client.get(self.HISTORY_CACHE_KEY)
            if not history or "snapshots" not in history:
                # Fallback to file cache
                history = self._load_history_file()
            if not history or "snapshots" not in history:
                history = {"snapshots": {}}

            date_key = data.get("date")
            if date_key:
                history["snapshots"][date_key] = {
                    "date": date_key,
                    "data": data.get("data", []),
                    "last_updated": data.get("last_updated")
                }

                # Keep only last 30 days
                snapshot_dates = sorted(history["snapshots"].keys(), reverse=True)
                if len(snapshot_dates) > 30:
                    for old_date in snapshot_dates[30:]:
                        del history["snapshots"][old_date]

                redis_client.set(self.HISTORY_CACHE_KEY, history, expire=0)

                # Also save to file
                self._save_history_file(history)
                print(f"Saved daily snapshot for {date_key}")

        except Exception as e:
            print(f"Error saving daily snapshot: {e}")

    def _get_previous_day_data(self) -> Optional[Dict]:
        """Get previous business day's OIS data from history"""
        try:
            history = redis_client.get(self.HISTORY_CACHE_KEY)
            if not history or "snapshots" not in history:
                history = self._load_history_file()

            if not history or "snapshots" not in history:
                return None

            snapshot_dates = sorted(history["snapshots"].keys(), reverse=True)
            today_str = datetime.now(JST).strftime("%Y-%m-%d")

            for date_str in snapshot_dates:
                if date_str != today_str:
                    return history["snapshots"][date_str]

            return None

        except Exception as e:
            print(f"Error getting previous day data: {e}")
            return None

    def get_eurex_ois_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get Eurex OIS data with caching
        Returns both current and previous day data for comparison
        """
        # Check cache
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    # キャッシュにpreviousがない場合は追加
                    if "previous" not in cached_data:
                        previous_data = self._get_previous_day_data()
                        if previous_data:
                            cached_data["previous"] = {
                                "date": previous_data.get("date"),
                                "data": previous_data.get("data", [])
                            }
                    return {
                        **cached_data,
                        "cached": True,
                        "source": "redis"
                    }

        # Fetch new data
        data_list = self._fetch_eurex_data()

        if data_list:
            today_str = datetime.now(JST).strftime("%Y-%m-%d")

            current_data = {
                "date": today_str,
                "data": data_list,
                "last_updated": datetime.now(JST).isoformat()
            }

            # Save daily snapshot
            self._save_daily_snapshot(current_data)

            # Get previous day data
            previous_data = self._get_previous_day_data()

            result = {
                "current": {
                    "date": today_str,
                    "data": data_list
                },
                "last_updated": datetime.now(JST).isoformat(),
                "source": "eurex"
            }

            if previous_data:
                result["previous"] = {
                    "date": previous_data.get("date"),
                    "data": previous_data.get("data", [])
                }

            # Save to cache
            redis_client.set(self.DATA_CACHE_KEY, result, expire=0)
            self._save_file_cache(result)

            return {**result, "cached": False, "source": "eurex"}

        # Fallback to file cache
        file_cache = self._load_file_cache()
        if file_cache:
            # ファイルキャッシュにもpreviousがない場合は追加
            if "previous" not in file_cache:
                previous_data = self._get_previous_day_data()
                if previous_data:
                    file_cache["previous"] = {
                        "date": previous_data.get("date"),
                        "data": previous_data.get("data", [])
                    }
            return {
                **file_cache,
                "cached": True,
                "source": "file (fallback)"
            }

        return {
            "current": {"date": None, "data": []},
            "last_updated": datetime.now(JST).isoformat(),
            "cached": False,
            "source": "none",
            "error": "Failed to fetch Eurex OIS data"
        }

    def get_chart_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get Eurex OIS chart data formatted for frontend
        Filters to show only future contract months (next 12 months)
        """
        data = self.get_eurex_ois_data(force_refresh=force_refresh)

        if not data or "current" not in data or not data["current"].get("data"):
            return {
                "labels": [],
                "values": [],
                "contracts": [],
                "settle_values": [],
                "previous_values": [],
                "last_updated": data.get("last_updated"),
                "source": data.get("source", "Eurex"),
                "current_date": None,
                "previous_date": None
            }

        current_data = data["current"]["data"]
        current_date = data["current"].get("date")

        # Filter to only future contracts (sort_date >= today)
        today_str = datetime.now(JST).strftime("%Y-%m-%d")
        future_data = [
            point for point in current_data
            if point.get("sort_date", "9999-99-99") >= today_str
        ]

        # Limit to 12 months ahead
        future_data = future_data[:12]

        labels = [point["date"] for point in future_data]
        values = [point["implied_rate"] for point in future_data]
        contracts = [point["contract"] for point in future_data]
        settle_values = [point["settle"] for point in future_data]

        previous_values = []
        previous_date = None

        if "previous" in data and data["previous"] and data["previous"].get("data"):
            previous_data = data["previous"]["data"]
            previous_date = data["previous"].get("date")
            prev_map = {point["contract"]: point["implied_rate"] for point in previous_data}
            previous_values = [prev_map.get(contract, None) for contract in contracts]

        return {
            "labels": labels,
            "values": values,
            "contracts": contracts,
            "settle_values": settle_values,
            "previous_values": previous_values,
            "last_updated": data.get("last_updated"),
            "source": data.get("source", "Eurex"),
            "current_date": current_date,
            "previous_date": previous_date
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """Check if cache should be refreshed"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # Skip weekends
            if now.weekday() >= 5:
                return False

            # If cached data is from today after update window, no refresh needed
            is_summer = self._is_dst(now)
            update_hour = 20 if is_summer else 21

            if (last_updated.date() == now.date() and last_updated.hour >= update_hour):
                return False

            # If in update window and cache is old, refresh
            if self.is_update_time():
                return True

            # If after update window today and cache is from before today
            if now.hour >= update_hour and last_updated.date() < now.date():
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """Load file cache"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            # 前環境のキャッシュフォーマット対応
            # { cached_at: ..., data: { date: ..., data: [...], ... } }
            if "cached_at" in raw_data and "data" in raw_data:
                inner_data = raw_data["data"]
                return {
                    "current": {
                        "date": inner_data.get("date"),
                        "data": inner_data.get("data", [])
                    },
                    "last_updated": inner_data.get("last_updated") or raw_data.get("cached_at"),
                    "source": inner_data.get("source", "Eurex")
                }

            return raw_data
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """Save file cache"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def _load_history_file(self) -> Optional[Dict[str, Any]]:
        """Load history file cache"""
        try:
            if not HISTORY_CACHE_FILE.exists():
                return None
            with open(HISTORY_CACHE_FILE, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            # 前環境のキャッシュフォーマット対応
            # { cached_at: ..., data: { snapshots: {...} } }
            if "cached_at" in raw_data and "data" in raw_data:
                return raw_data["data"]

            return raw_data
        except Exception as e:
            print(f"Failed to load history file: {e}")
            return None

    def _save_history_file(self, data: Dict[str, Any]) -> None:
        """Save history file cache"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save history file: {e}")

    def invalidate_cache(self) -> bool:
        """Invalidate cache"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Eurex Three-Month Euro STR Futures OIS",
            "source": "Eurex",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "current_date": cached_data.get("current", {}).get("date") if cached_data else None,
            "data_count": len(cached_data.get("current", {}).get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
eurex_ois_service = EurexOISService()
