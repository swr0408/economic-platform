"""
中国 百度迁徙（Baidu Migration）人流総量 Screenshot Service
百度地图慧眼のチャートをSeleniumでスクリーンショット取得

URL:
- https://qianxi.baidu.com/#/

Target CSS: .mgs-line
スクリーンショット前にJS実行でチャート高さ・凡例位置を調整
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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# スクリーンショットファイル名
SCREENSHOT_FILENAME = "cn_baidu_migration.png"
SCREENSHOT_PATH = CACHE_DIR / SCREENSHOT_FILENAME

# スクリーンショット対象URL
SCREENSHOT_URL = "https://qianxi.baidu.com/#/"

# チャートレイアウト調整用JS
LAYOUT_ADJUST_JS = """
(function() {
    var root = document.querySelector('.mgs-line');
    if (!root) return false;

    // ルート要素: overflow hidden で背景の地図を隠す
    root.style.overflow = 'hidden';
    root.style.height = '500px';
    root.style.position = 'relative';
    root.style.zIndex = '999';
    root.style.backgroundColor = '#242b3a';

    // echarts DOM の高さを拡大
    var chartDom = root.querySelector('[_echarts_instance_]');
    if (chartDom) {
        chartDom.style.height = '430px';
    }

    // 右下のマスコット削除
    var mascot = document.getElementById('floatGuaJian');
    if (mascot) mascot.remove();

    // echarts: 凡例位置調整 + grid拡大 + リサイズ
    if (chartDom && typeof echarts !== 'undefined') {
        var chart = echarts.getInstanceByDom(chartDom);
        if (chart) {
            var option = chart.getOption();
            if (Array.isArray(option.legend)) {
                option.legend.forEach(function(legend) {
                    legend.top = 40;
                });
            }
            if (Array.isArray(option.grid)) {
                option.grid.forEach(function(g) {
                    g.bottom = 40;
                });
            }
            chart.setOption(option);
            chart.resize();
        }
    }

    return true;
})();
"""


class CnBaiduMigrationScreenshotService:
    """China Baidu Migration (人流総量) Screenshot Service"""

    CACHE_KEY = "china:baidu_migration_screenshot:metadata"

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
        chrome_options.add_argument('--lang=zh-CN')
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
        """Capture screenshot from Baidu Migration page"""
        driver = None
        try:
            driver = self._create_driver()

            print(f"[BaiduMigration] Accessing {url}")
            driver.get(url)

            print("[BaiduMigration] Waiting for page to load...")
            time.sleep(8)

            # チャートコンテナが読み込まれるのを待つ
            try:
                wait = WebDriverWait(driver, 20)
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".mgs-line")
                    )
                )
                print("[BaiduMigration] Chart container (.mgs-line) found")
                time.sleep(3)
            except Exception as e:
                print(f"[BaiduMigration] Could not find chart container: {e}")

            # canvasが描画されるのを待つ
            try:
                wait = WebDriverWait(driver, 10)
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".mgs-line canvas")
                    )
                )
                print("[BaiduMigration] Canvas element found")
                time.sleep(2)
            except Exception as e:
                print(f"[BaiduMigration] Could not find canvas: {e}")

            # レイアウト調整JS実行
            try:
                result = driver.execute_script(LAYOUT_ADJUST_JS)
                print(f"[BaiduMigration] Layout adjustment executed: {result}")
                time.sleep(2)
            except Exception as e:
                print(f"[BaiduMigration] Layout adjustment failed: {e}")

            # スクロールして表示
            try:
                chart_element = driver.find_element(By.CSS_SELECTOR, ".mgs-line")
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", chart_element
                )
                print("[BaiduMigration] Scrolled to chart")
                time.sleep(1)
            except Exception as e:
                print(f"[BaiduMigration] Could not scroll to chart: {e}")

            # 要素スクリーンショット
            try:
                chart_element = driver.find_element(By.CSS_SELECTOR, ".mgs-line")
                chart_element.screenshot(str(output_path))
                print(f"[BaiduMigration] Screenshot saved to {output_path}")
                return True
            except Exception as e:
                print(f"[BaiduMigration] Failed to capture element screenshot: {e}")
                print("[BaiduMigration] Falling back to full page screenshot")
                driver.save_screenshot(str(output_path))
                return True

        except Exception as e:
            print(f"[BaiduMigration] Error capturing screenshot from {url}: {e}")
            return False

        finally:
            if driver:
                driver.quit()
                print("[BaiduMigration] Browser closed")

    def capture_screenshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Capture Baidu Migration screenshot"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)

        # キャッシュチェック（24時間）
        if not force_refresh and SCREENSHOT_PATH.exists():
            file_age = now.timestamp() - SCREENSHOT_PATH.stat().st_mtime
            if file_age < 86400:
                print(f"[BaiduMigration] Using cached screenshot (age: {file_age/3600:.1f} hours)")
                return {
                    "success": True,
                    "url": f"/cache/china/economy/{SCREENSHOT_FILENAME}",
                    "cached": True,
                    "last_updated": self._get_last_updated(),
                }

        # スクリーンショット取得
        print("[BaiduMigration] Capturing Baidu Migration screenshot...")
        success = self._capture_screenshot(SCREENSHOT_URL, SCREENSHOT_PATH)

        result = {
            "success": success,
            "url": f"/cache/china/economy/{SCREENSHOT_FILENAME}" if success else None,
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
            result["screenshot_url"] = f"/cache/china/economy/{SCREENSHOT_FILENAME}"

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
            "indicator": "China Baidu Migration (Total Number of People)",
            "source": "百度地图慧眼",
            "cache_key": self.CACHE_KEY,
            "screenshot_exists": SCREENSHOT_PATH.exists(),
            "last_updated": self._get_last_updated(),
        }

    def invalidate_cache(self) -> bool:
        """Invalidate screenshot cache"""
        redis_client.delete(self.CACHE_KEY)
        return True


# シングルトンインスタンス
cn_baidu_migration_screenshot_service = CnBaiduMigrationScreenshotService()
