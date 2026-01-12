"""
ECB Rate Cuts Expectation Screenshot Service
Captures screenshots from MacroMicro charts using Selenium

URLs (2026年):
- 年末金利予想: https://en.macromicro.me/series/78279/euro-area-ecb-year-end-interest-rate-expectation-2026
- 利上げ・利下げ回数: https://en.macromicro.me/series/78285/euro-area-ecb-interest-rate-cuts-expectation-2026

Target: main tab > class="mm-cc-bd" > class="container chart-theater is-stat"
"""
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリの設定
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "eurozone" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# スクリーンショットファイル名
YEAREND_SCREENSHOT_FILENAME = "ecb_yearend_rate_expectations.png"
RATE_CUTS_SCREENSHOT_FILENAME = "ecb_rate_cuts_expectations.png"

YEAREND_SCREENSHOT_PATH = CACHE_DIR / YEAREND_SCREENSHOT_FILENAME
RATE_CUTS_SCREENSHOT_PATH = CACHE_DIR / RATE_CUTS_SCREENSHOT_FILENAME

# スクリーンショット対象URL（2026年版 - ECB専用ページ）
YEAREND_URL = "https://en.macromicro.me/series/78279/euro-area-ecb-year-end-interest-rate-expectation-2026"
RATE_CUTS_URL = "https://en.macromicro.me/series/78285/euro-area-ecb-interest-rate-cuts-expectation-2026"


class ECBRateCutsScreenshotService:
    """ECB Rate Cuts Expectation Screenshot Service"""

    CACHE_KEY = "eurozone:ecb_rate_cuts_screenshot:metadata"

    def __init__(self):
        pass

    def _create_driver(self) -> webdriver.Chrome:
        """Create Chrome WebDriver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1400')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Docker環境では/usr/bin/chromiumを使用
        if os.path.exists('/usr/bin/chromium'):
            chrome_options.binary_location = '/usr/bin/chromium'
            from webdriver_manager.core.os_manager import ChromeType
            service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        else:
            service = Service(ChromeDriverManager().install())

        return webdriver.Chrome(service=service, options=chrome_options)

    def _capture_screenshot(self, url: str, output_path: Path) -> bool:
        """
        Capture screenshot from MacroMicro chart page

        Args:
            url: Target URL
            output_path: Path to save screenshot

        Returns:
            True if successful, False otherwise
        """
        driver = None
        try:
            driver = self._create_driver()

            print(f"Accessing {url}")
            driver.get(url)

            # ページが完全に読み込まれるまで待機
            print("Waiting for page to load...")
            time.sleep(5)

            # チャートコンテナが読み込まれるのを待つ
            try:
                wait = WebDriverWait(driver, 15)
                chart_container = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".mm-cc-bd .container.chart-theater.is-stat"))
                )
                print("Chart container found")
                time.sleep(3)  # チャートの描画完了を待つ
            except Exception as e:
                print(f"Could not find chart container: {e}")

            # チャートを画面内に収める
            try:
                chart_element = driver.find_element(By.CSS_SELECTOR, ".mm-cc-bd .container.chart-theater.is-stat")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", chart_element)
                print("Scrolled to chart")
                time.sleep(2)
            except Exception as e:
                print(f"Could not scroll to chart: {e}")

            # 対象要素のスクリーンショットを取得
            try:
                chart_element = driver.find_element(By.CSS_SELECTOR, ".mm-cc-bd .container.chart-theater.is-stat")
                chart_element.screenshot(str(output_path))
                print(f"Screenshot saved to {output_path}")
                return True
            except Exception as e:
                print(f"Failed to capture element screenshot: {e}")
                # フォールバック: ページ全体のスクリーンショット
                print("Falling back to full page screenshot")
                driver.save_screenshot(str(output_path))
                return True

        except Exception as e:
            print(f"Error capturing screenshot from {url}: {e}")
            return False

        finally:
            if driver:
                driver.quit()
                print("Browser closed")

    def capture_all_screenshots(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Capture all ECB rate expectation screenshots

        Args:
            force_refresh: Force new screenshots even if cache is recent

        Returns:
            Status dictionary with screenshot URLs
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)
        results = {
            "yearend": {"success": False, "url": None, "cached": False},
            "rate_cuts": {"success": False, "url": None, "cached": False},
            "last_updated": None
        }

        # キャッシュチェック
        if not force_refresh:
            # 24時間以内のキャッシュがあれば再利用
            if YEAREND_SCREENSHOT_PATH.exists():
                file_age = now.timestamp() - YEAREND_SCREENSHOT_PATH.stat().st_mtime
                if file_age < 86400:  # 24時間
                    results["yearend"] = {
                        "success": True,
                        "url": f"/cache/eurozone/monetary_policy/{YEAREND_SCREENSHOT_FILENAME}",
                        "cached": True
                    }
                    print(f"Using cached yearend screenshot (age: {file_age/3600:.1f} hours)")

            if RATE_CUTS_SCREENSHOT_PATH.exists():
                file_age = now.timestamp() - RATE_CUTS_SCREENSHOT_PATH.stat().st_mtime
                if file_age < 86400:
                    results["rate_cuts"] = {
                        "success": True,
                        "url": f"/cache/eurozone/monetary_policy/{RATE_CUTS_SCREENSHOT_FILENAME}",
                        "cached": True
                    }
                    print(f"Using cached rate_cuts screenshot (age: {file_age/3600:.1f} hours)")

            # 両方キャッシュがあればそのまま返す
            if results["yearend"]["cached"] and results["rate_cuts"]["cached"]:
                cached_meta = redis_client.get(self.CACHE_KEY)
                results["last_updated"] = cached_meta.get("last_updated") if cached_meta else now.isoformat()
                return results

        # 年末金利予想スクリーンショット
        if not results["yearend"]["cached"]:
            print("Capturing yearend rate expectations screenshot...")
            success = self._capture_screenshot(YEAREND_URL, YEAREND_SCREENSHOT_PATH)
            results["yearend"] = {
                "success": success,
                "url": f"/cache/eurozone/monetary_policy/{YEAREND_SCREENSHOT_FILENAME}" if success else None,
                "cached": False
            }

        # 利上げ・利下げ回数スクリーンショット
        if not results["rate_cuts"]["cached"]:
            print("Capturing rate cuts expectations screenshot...")
            success = self._capture_screenshot(RATE_CUTS_URL, RATE_CUTS_SCREENSHOT_PATH)
            results["rate_cuts"] = {
                "success": success,
                "url": f"/cache/eurozone/monetary_policy/{RATE_CUTS_SCREENSHOT_FILENAME}" if success else None,
                "cached": False
            }

        results["last_updated"] = now.isoformat()

        # メタデータをRedisに保存
        redis_client.set(self.CACHE_KEY, {
            "last_updated": now.isoformat(),
            "yearend_exists": YEAREND_SCREENSHOT_PATH.exists(),
            "rate_cuts_exists": RATE_CUTS_SCREENSHOT_PATH.exists()
        }, expire=0)

        return results

    def get_screenshot_urls(self) -> Dict[str, Any]:
        """
        Get URLs for cached screenshots

        Returns:
            Dictionary with screenshot URLs and metadata
        """
        result = {
            "yearend_url": None,
            "rate_cuts_url": None,
            "last_updated": None
        }

        if YEAREND_SCREENSHOT_PATH.exists():
            result["yearend_url"] = f"/cache/eurozone/monetary_policy/{YEAREND_SCREENSHOT_FILENAME}"

        if RATE_CUTS_SCREENSHOT_PATH.exists():
            result["rate_cuts_url"] = f"/cache/eurozone/monetary_policy/{RATE_CUTS_SCREENSHOT_FILENAME}"

        cached_meta = redis_client.get(self.CACHE_KEY)
        if cached_meta:
            result["last_updated"] = cached_meta.get("last_updated")
        elif YEAREND_SCREENSHOT_PATH.exists():
            # ファイルの更新日時を使用
            mtime = datetime.fromtimestamp(YEAREND_SCREENSHOT_PATH.stat().st_mtime, tz=JST)
            result["last_updated"] = mtime.isoformat()

        return result

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status for screenshots"""
        cached_meta = redis_client.get(self.CACHE_KEY)

        return {
            "indicator": "ECB Rate Cuts Expectations Screenshots",
            "source": "MacroMicro",
            "cache_key": self.CACHE_KEY,
            "yearend_exists": YEAREND_SCREENSHOT_PATH.exists(),
            "rate_cuts_exists": RATE_CUTS_SCREENSHOT_PATH.exists(),
            "last_updated": cached_meta.get("last_updated") if cached_meta else None
        }

    def invalidate_cache(self) -> bool:
        """Invalidate screenshot cache"""
        redis_client.delete(self.CACHE_KEY)
        # ファイルは削除しない（次回リクエストで更新される）
        return True


# シングルトンインスタンス
ecb_rate_cuts_screenshot_service = ECBRateCutsScreenshotService()
