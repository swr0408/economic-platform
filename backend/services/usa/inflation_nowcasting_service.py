"""
インフレーションナウキャスティングサービス
Cleveland FedのInflation Nowcastingデータを取得

指標:
- CPI, Core CPI, PCE, Core PCE の予測値
- 月次の前月比（MoM）と前年比（YoY）

データソース:
- Cleveland Fed: https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting

発表スケジュール:
- 毎営業日 10:00 ET頃

キャッシュ方式: 毎日更新（営業日に3分間隔でチェック）
"""
import json
import time
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
INFLATION_NOWCASTING_CACHE_FILE = CACHE_DIR / "inflation_nowcasting_cache.json"

# Cleveland Fed Inflation Nowcasting URL
CLEVELAND_FED_URL = "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"


class InflationNowcastingService:
    """インフレーションナウキャスティングサービス"""

    DATA_CACHE_KEY = "inflation:nowcasting:data"

    def __init__(self):
        pass

    def get_inflation_nowcasting_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        インフレーションナウキャスティングデータを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            ナウキャスティングデータ（MoM, YoY）
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "monthly_mom": cached_data.get("monthly_mom", []),
                        "monthly_yoy": cached_data.get("monthly_yoy", []),
                        "last_updated": last_updated_str,
                        "cached": True,
                        "source": "redis"
                    }

        # Cleveland Fedからスクレイピング
        scrape_result = self._scrape_cleveland_fed()
        if scrape_result and (scrape_result.get("monthly_mom") or scrape_result.get("monthly_yoy")):
            cache_payload = {
                "monthly_mom": scrape_result.get("monthly_mom", []),
                "monthly_yoy": scrape_result.get("monthly_yoy", []),
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "monthly_mom": scrape_result.get("monthly_mom", []),
                "monthly_yoy": scrape_result.get("monthly_yoy", []),
                "last_updated": datetime.now(JST).isoformat(),
                "cached": False,
                "source": "cleveland_fed"
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "monthly_mom": file_cache.get("monthly_mom", []),
                "monthly_yoy": file_cache.get("monthly_yoy", []),
                "last_updated": file_cache.get("last_updated"),
                "cached": True,
                "source": "file (fallback)"
            }

        return {
            "monthly_mom": [],
            "monthly_yoy": [],
            "last_updated": None,
            "cached": False,
            "source": "none",
            "error": "No data available"
        }

    def _scrape_cleveland_fed(self) -> Optional[Dict[str, Any]]:
        """Cleveland FedのページからSeleniumでデータをスクレイピング"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            print(f"Fetching Cleveland Fed Inflation Nowcasting: {CLEVELAND_FED_URL}")

            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')

            driver = None
            try:
                # Docker環境用: chromedriverのパスを指定
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    service = Service(ChromeDriverManager().install())
                except Exception:
                    # Docker環境ではchromedriverがインストール済み
                    service = Service('/usr/bin/chromedriver')

                driver = webdriver.Chrome(service=service, options=options)
                driver.get(CLEVELAND_FED_URL)

                # ページの読み込みを待つ
                wait = WebDriverWait(driver, 20)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                time.sleep(2)  # JavaScriptの実行を待つ

                # テーブルを取得
                tables = driver.find_elements(By.TAG_NAME, "table")

                mom_data = []
                yoy_data = []

                if len(tables) >= 2:
                    # Table 0: Month-over-Month
                    mom_data = self._parse_table_element(tables[0])
                    # Table 1: Year-over-Year
                    yoy_data = self._parse_table_element(tables[1])

                print(f"Parsed MoM data: {len(mom_data)} rows")
                print(f"Parsed YoY data: {len(yoy_data)} rows")

                return {
                    "monthly_mom": mom_data,
                    "monthly_yoy": yoy_data
                }

            finally:
                if driver:
                    driver.quit()

        except ImportError:
            print("Selenium not available, trying requests fallback")
            return self._scrape_with_requests()
        except Exception as e:
            print(f"Error scraping Cleveland Fed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _scrape_with_requests(self) -> Optional[Dict[str, Any]]:
        """requestsを使用したフォールバック（JavaScriptレンダリング不要な場合）"""
        try:
            import requests
            from bs4 import BeautifulSoup

            response = requests.get(CLEVELAND_FED_URL, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            tables = soup.find_all('table')

            if len(tables) < 2:
                print("Not enough tables found with requests")
                return None

            mom_data = self._parse_bs4_table(tables[0])
            yoy_data = self._parse_bs4_table(tables[1])

            return {
                "monthly_mom": mom_data,
                "monthly_yoy": yoy_data
            }

        except Exception as e:
            print(f"Error with requests fallback: {e}")
            return None

    def _parse_table_element(self, table_element) -> List[Dict[str, Any]]:
        """
        Selenium WebElementからテーブルデータを解析

        Args:
            table_element: Selenium WebElement (table)

        Returns:
            List[Dict]: 解析されたデータ
        """
        result = []

        try:
            table_text = table_element.text
            lines = table_text.strip().split('\n')

            if len(lines) < 3:
                return result

            # ヘッダー行を探す
            headers = None
            data_start_idx = 0

            for i, line in enumerate(lines):
                if 'Month' in line and 'CPI' in line:
                    headers = line.split()
                    data_start_idx = i + 1
                    break
                elif 'Quarter' in line and 'CPI' in line:
                    headers = line.split()
                    data_start_idx = i + 1
                    break

            if not headers:
                return result

            # データ行を解析
            for i in range(data_start_idx, len(lines)):
                line = lines[i]

                if line.startswith('Note:'):
                    break

                if not line.strip():
                    continue

                parts = line.split()

                if len(parts) < 2:
                    continue

                row_data = {}

                # 日付列の解析
                if len(parts) >= 2:
                    if ':Q' in parts[0]:  # Quarterly format "2025:Q3"
                        row_data['date'] = parts[0]
                        value_start_idx = 1
                    else:  # Monthly format "October 2025"
                        row_data['date'] = f"{parts[0]} {parts[1]}"
                        value_start_idx = 2

                    values = parts[value_start_idx:]

                    # Updated列を除外
                    if len(values) > 4:
                        values = values[:4]

                    # CPI, Core CPI, PCE, Core PCE
                    if len(values) >= 4:
                        try:
                            row_data['cpi'] = float(values[0]) if values[0] not in ['', '-'] else None
                            row_data['core_cpi'] = float(values[1]) if values[1] not in ['', '-'] else None
                            row_data['pce'] = float(values[2]) if values[2] not in ['', '-'] else None
                            row_data['core_pce'] = float(values[3]) if values[3] not in ['', '-'] else None
                        except (ValueError, IndexError):
                            continue

                    if 'date' in row_data and any(v is not None for v in [
                        row_data.get('cpi'),
                        row_data.get('core_cpi'),
                        row_data.get('pce'),
                        row_data.get('core_pce')
                    ]):
                        result.append(row_data)

        except Exception as e:
            print(f"Error parsing table element: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _parse_bs4_table(self, table) -> List[Dict[str, Any]]:
        """BeautifulSoupでテーブルを解析"""
        result = []

        try:
            rows = table.find_all('tr')

            for row in rows[1:]:  # ヘッダーをスキップ
                cells = row.find_all(['td', 'th'])
                if len(cells) < 5:
                    continue

                row_data = {
                    'date': cells[0].get_text(strip=True)
                }

                try:
                    cpi_text = cells[1].get_text(strip=True)
                    row_data['cpi'] = float(cpi_text) if cpi_text not in ['', '-'] else None
                except (ValueError, IndexError):
                    row_data['cpi'] = None

                try:
                    core_cpi_text = cells[2].get_text(strip=True)
                    row_data['core_cpi'] = float(core_cpi_text) if core_cpi_text not in ['', '-'] else None
                except (ValueError, IndexError):
                    row_data['core_cpi'] = None

                try:
                    pce_text = cells[3].get_text(strip=True)
                    row_data['pce'] = float(pce_text) if pce_text not in ['', '-'] else None
                except (ValueError, IndexError):
                    row_data['pce'] = None

                try:
                    core_pce_text = cells[4].get_text(strip=True)
                    row_data['core_pce'] = float(core_pce_text) if core_pce_text not in ['', '-'] else None
                except (ValueError, IndexError):
                    row_data['core_pce'] = None

                if any(v is not None for v in [row_data.get('cpi'), row_data.get('core_cpi'),
                                                row_data.get('pce'), row_data.get('core_pce')]):
                    result.append(row_data)

        except Exception as e:
            print(f"Error parsing BS4 table: {e}")

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        毎営業日10:00 ET以降に更新チェック

        Args:
            last_updated_str: 最終更新日時（ISO形式）

        Returns:
            更新すべき場合True
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            today = date.today()

            # 営業日（月-金）のみチェック
            if today.weekday() >= 5:  # 土日
                return False

            # 10:00 ET = 約00:00 JST（翌日）または 23:00 JST（夏時間）
            release_time_et = datetime(
                today.year, today.month, today.day,
                10, 0, 0,
                tzinfo=ET
            )
            release_time_jst = release_time_et.astimezone(JST)

            # 発表時刻後かつキャッシュが発表前の場合
            if now >= release_time_jst and last_updated < release_time_jst:
                return True

            # キャッシュが1日以上前の場合も更新
            time_diff = now - last_updated
            if time_diff.total_seconds() > 24 * 60 * 60:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh condition: {e}")
            return False

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not INFLATION_NOWCASTING_CACHE_FILE.exists():
                return None
            with open(INFLATION_NOWCASTING_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(INFLATION_NOWCASTING_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Inflation Nowcasting",
            "source": "Cleveland Fed",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "mom_count": len(cached_data.get("monthly_mom", [])) if cached_data else 0,
            "yoy_count": len(cached_data.get("monthly_yoy", [])) if cached_data else 0,
            "file_cache_exists": INFLATION_NOWCASTING_CACHE_FILE.exists()
        }


# シングルトンインスタンス
inflation_nowcasting_service = InflationNowcastingService()
