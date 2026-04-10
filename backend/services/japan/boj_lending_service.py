"""
日銀貸出動向サービス（Bank of Japan Lending Trends）

データソース: 日本銀行 統計検索サイト
データコード: FAAPOBAL1（貸出動向・銀行計）
URL: https://www.stat-search.boj.or.jp/ssi/cgi-bin/famecgi2?cgi=$nme_a000&lstSelection=MD13

キャッシュ方式: Redis + ファイルフォールバック
更新: 毎月（月末から翌月初に公表）
スケジュール: 毎月1日から毎日9:30 JSTにチェック、更新したら以降スキップ

Playwright (BrowserRunner) を使用して BOJ 統計検索サイトからデータを取得。
multi-window フロー (チェックボックス → 抽出条件追加 → 抽出 → ダウンロード →
CSV リンク取得) を run_custom_flow 経由で実行する。
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

try:
    from backend.services.browser import BrowserConfig, run_custom_flow
except ImportError:
    from services.browser import BrowserConfig, run_custom_flow

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

    def _fetch_lending_data(self) -> Optional[List[Dict[str, Any]]]:
        """
        Playwright (run_custom_flow) を使って BOJ 統計検索サイトからデータを取得。

        multi-window フロー:
          1. メインページ → 展開 → チェックボックス選択
          2. 抽出条件追加 → 開始年設定 → 抽出ボタン → 新しいウィンドウ
          3. ダウンロードボタン → 3 つ目のウィンドウ → CSV リンク取得
          4. requests.get() で CSV ダウンロード → pandas で解析

        Returns:
            List of data points with date and value, or None if failed
        """
        import requests
        from io import StringIO
        import pandas as pd

        config = BrowserConfig(
            viewport=(1920, 1080),
            locale="ja-JP",
        )

        def _boj_flow(context) -> Optional[str]:
            """BrowserContext を使って CSV ダウンロード URL を返す。"""
            page = context.new_page()

            try:
                # Step 1: Navigate
                logger.info(f"Navigating to {self.BOJ_STAT_LENDING_URL}")
                page.goto(self.BOJ_STAT_LENDING_URL, wait_until="networkidle")
                page.wait_for_selector(".searchCondition")
                logger.info("Page loaded successfully")

                # Step 2: Click expand button
                logger.info("Clicking expand button")
                try:
                    expand_sel = '#menuSearchTabpanel >> xpath=div[2]/div[1]/div[2]/input'
                    page.click(expand_sel, timeout=10_000)
                except Exception:
                    # フォールバック: input[type="button"] で展開ボタンを探す
                    try:
                        page.click(
                            '#menuSearchTabpanel input[type="button"]',
                            timeout=5_000,
                        )
                    except Exception as e:
                        logger.warning(f"Could not find expand button: {e}")

                page.wait_for_selector(".tableDataCode", timeout=10_000)
                logger.info("Data list loaded")

                # Step 3: Find and check FAAPOBAL1
                full_code = f"MD13'{self.DATA_CODE}"
                logger.info(f"Looking for data code: {full_code}")

                checkbox = page.query_selector(f'input[value="{full_code}"]')
                if not checkbox:
                    checkbox = page.query_selector(f'#{full_code}')
                if not checkbox:
                    # 全 searchDataCode チェックボックスを走査
                    for cb in page.query_selector_all('input[type="checkbox"].searchDataCode'):
                        val = cb.get_attribute("value") or ""
                        if self.DATA_CODE in val:
                            checkbox = cb
                            break

                if not checkbox:
                    logger.error(f"Could not find checkbox for {self.DATA_CODE}")
                    return None

                checkbox.scroll_into_view_if_needed()
                checkbox.click()
                logger.info(f"Selected {self.DATA_CODE}")

                # Step 4: Click "抽出条件に追加"
                add_btn = page.query_selector('a[onclick*="addAbstractCondition"]')
                if not add_btn:
                    add_btn = page.query_selector('a:has-text("抽出条件に追加")')
                if not add_btn:
                    for btn in page.query_selector_all("a.largeButton"):
                        if "抽出条件に追加" in (btn.inner_text() or ""):
                            add_btn = btn
                            break

                if not add_btn:
                    logger.error("Could not find '抽出条件に追加' button")
                    return None

                add_btn.click()
                page.wait_for_selector("#resultArea", timeout=5_000)
                logger.info("Added to extraction conditions")

                # Step 5: Set start year
                try:
                    page.fill("#fromYear", "2010")
                    logger.info("Set start year to 2010")
                except Exception as e:
                    logger.warning(f"Could not set fromYear: {e}")

                # Step 6: Click extraction → opens new window (popup)
                extract_btn = page.query_selector('a[onclick*="submit_code_main"]')
                if not extract_btn:
                    for link in page.query_selector_all("a.middleButton"):
                        if "抽出" in (link.inner_text() or ""):
                            extract_btn = link
                            break

                if not extract_btn:
                    logger.error("Could not find '抽出' button")
                    return None

                with context.expect_page() as popup_info:
                    extract_btn.click()
                extract_page = popup_info.value
                extract_page.wait_for_load_state("networkidle")
                logger.info("Switched to extraction window")

                # Step 7: Click download → opens third window
                dl_btn = extract_page.query_selector('a[onclick*="DLform_MM.submit"]')
                if not dl_btn:
                    dl_btn = extract_page.locator('a:has-text("ダウンロード")').first
                    if not dl_btn:
                        logger.error("Could not find download button")
                        extract_page.close()
                        return None

                with context.expect_page() as dl_popup_info:
                    dl_btn.click()
                dl_page = dl_popup_info.value
                dl_page.wait_for_load_state("networkidle")
                logger.info(f"Download window URL: {dl_page.url}")

                # Step 8: Get CSV link
                csv_link = dl_page.query_selector('a:has-text("CSV")')
                if not csv_link:
                    # フォールバック: download / dl を含むリンク
                    for a in dl_page.query_selector_all("a"):
                        href = a.get_attribute("href") or ""
                        if "download" in href.lower() or "dl" in href.lower():
                            csv_link = a
                            break

                csv_url = None
                if csv_link:
                    href = csv_link.get_attribute("href")
                    csv_url = urljoin(dl_page.url, href) if href else None

                # cleanup
                dl_page.close()
                extract_page.close()

                if not csv_url:
                    logger.error("Could not find CSV download URL")
                    return None

                logger.info(f"CSV download URL: {csv_url}")
                return csv_url

            except Exception as e:
                logger.error(f"Error in BOJ flow: {e}", exc_info=True)
                return None
            finally:
                try:
                    page.close()
                except Exception:
                    pass

        try:
            logger.info("Starting Playwright data fetch for BOJ Lending")
            csv_url = run_custom_flow(_boj_flow, config=config)

            if not csv_url:
                return None

            # Step 9: Download CSV using requests
            logger.info(f"Downloading CSV from: {csv_url}")
            response = requests.get(csv_url, timeout=30)
            response.encoding = "shift_jis"

            df = pd.read_csv(StringIO(response.text))
            logger.info(f"Downloaded CSV with {len(df)} rows, {len(df.columns)} columns")
            return self._process_dataframe(df)

        except Exception as e:
            logger.error(f"Error fetching BOJ Lending data: {e}", exc_info=True)
            return None

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
        fetched_data = self._fetch_lending_data()
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
