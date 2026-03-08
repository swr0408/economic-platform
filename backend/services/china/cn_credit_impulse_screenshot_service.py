"""
中国クレジットインパルス Screenshot Service
MacroMicro のチャートをSeleniumでスクリーンショット取得

URL:
- https://en.macromicro.me/series/17516/cn-bloomberg-credit-impulse

Target CSS: .mm-cc-bd .container.chart-theater.is-stat
"""
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
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

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# スクリーンショットファイル名
SCREENSHOT_FILENAME = "cn_credit_impulse.png"
SCREENSHOT_PATH = CACHE_DIR / SCREENSHOT_FILENAME

# スクリーンショット対象URL
SCREENSHOT_URL = "https://en.macromicro.me/series/17516/cn-bloomberg-credit-impulse"


class CnCreditImpulseScreenshotService:
    """China Credit Impulse Screenshot Service"""

    CACHE_KEY = "china:credit_impulse_screenshot:metadata"

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
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        if os.path.exists('/usr/bin/chromium'):
            chrome_options.binary_location = '/usr/bin/chromium'
            from webdriver_manager.core.os_manager import ChromeType
            service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        else:
            service = Service(ChromeDriverManager().install())

        return webdriver.Chrome(service=service, options=chrome_options)

    def _capture_screenshot(self, url: str, output_path: Path) -> bool:
        """Capture screenshot from MacroMicro chart page"""
        driver = None
        try:
            driver = self._create_driver()

            print(f"[CnCreditImpulse] Accessing {url}")
            driver.get(url)

            print("[CnCreditImpulse] Waiting for page to load...")
            time.sleep(5)

            # チャートコンテナが読み込まれるのを待つ
            try:
                wait = WebDriverWait(driver, 15)
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".mm-cc-bd .container.chart-theater.is-stat")
                    )
                )
                print("[CnCreditImpulse] Chart container found")
                time.sleep(3)
            except Exception as e:
                print(f"[CnCreditImpulse] Could not find chart container: {e}")

            # スクロールして表示
            try:
                chart_element = driver.find_element(
                    By.CSS_SELECTOR, ".mm-cc-bd .container.chart-theater.is-stat"
                )
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", chart_element
                )
                print("[CnCreditImpulse] Scrolled to chart")
                time.sleep(2)
            except Exception as e:
                print(f"[CnCreditImpulse] Could not scroll to chart: {e}")

            # 要素スクリーンショット
            try:
                chart_element = driver.find_element(
                    By.CSS_SELECTOR, ".mm-cc-bd .container.chart-theater.is-stat"
                )
                chart_element.screenshot(str(output_path))
                print(f"[CnCreditImpulse] Screenshot saved to {output_path}")
                return True
            except Exception as e:
                print(f"[CnCreditImpulse] Failed to capture element screenshot: {e}")
                print("[CnCreditImpulse] Falling back to full page screenshot")
                driver.save_screenshot(str(output_path))
                return True

        except Exception as e:
            print(f"[CnCreditImpulse] Error capturing screenshot from {url}: {e}")
            return False

        finally:
            if driver:
                driver.quit()
                print("[CnCreditImpulse] Browser closed")

    def capture_screenshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Capture credit impulse screenshot"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)

        # キャッシュチェック（24時間）
        if not force_refresh and SCREENSHOT_PATH.exists():
            file_age = now.timestamp() - SCREENSHOT_PATH.stat().st_mtime
            if file_age < 86400:
                print(f"[CnCreditImpulse] Using cached screenshot (age: {file_age/3600:.1f} hours)")
                return {
                    "success": True,
                    "url": f"/cache/china/policy/{SCREENSHOT_FILENAME}",
                    "cached": True,
                    "last_updated": self._get_last_updated(),
                }

        # スクリーンショット取得
        print("[CnCreditImpulse] Capturing Credit Impulse screenshot...")
        success = self._capture_screenshot(SCREENSHOT_URL, SCREENSHOT_PATH)

        result = {
            "success": success,
            "url": f"/cache/china/policy/{SCREENSHOT_FILENAME}" if success else None,
            "cached": False,
            "last_updated": now.isoformat(),
        }

        # メタデータをRedisに保存
        redis_client.set(
            self.CACHE_KEY,
            {
                "last_updated": now.isoformat(),
                "screenshot_exists": SCREENSHOT_PATH.exists(),
            },
            expire=0,
        )

        return result

    def get_screenshot_url(self) -> Dict[str, Any]:
        """Get URL for cached screenshot"""
        result = {
            "screenshot_url": None,
            "last_updated": None,
        }

        if SCREENSHOT_PATH.exists():
            result["screenshot_url"] = f"/cache/china/policy/{SCREENSHOT_FILENAME}"

        result["last_updated"] = self._get_last_updated()

        return result

    def _get_last_updated(self) -> str | None:
        """Get last updated timestamp"""
        cached_meta = redis_client.get(self.CACHE_KEY)
        if cached_meta:
            return cached_meta.get("last_updated")

        if SCREENSHOT_PATH.exists():
            mtime = datetime.fromtimestamp(SCREENSHOT_PATH.stat().st_mtime, tz=JST)
            return mtime.isoformat()

        return None

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        return {
            "indicator": "China Credit Impulse Screenshot",
            "source": "MacroMicro",
            "cache_key": self.CACHE_KEY,
            "screenshot_exists": SCREENSHOT_PATH.exists(),
            "last_updated": self._get_last_updated(),
        }

    def invalidate_cache(self) -> bool:
        """Invalidate screenshot cache"""
        redis_client.delete(self.CACHE_KEY)
        return True


# シングルトンインスタンス
cn_credit_impulse_screenshot_service = CnCreditImpulseScreenshotService()
