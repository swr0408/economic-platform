"""
RBA OIS Screenshot Service
Captures screenshots from MacroMicro charts using Selenium

3枚のスクリーンショット:
- 1M OIS: https://en.macromicro.me/series/6287/australia-overnight-indexed-swaps-1-month
- 3M OIS: https://en.macromicro.me/series/6288/australia-overnight-indexed-swaps-3-month
- 6M OIS: https://en.macromicro.me/series/6289/australia-overnight-indexed-swaps-6-month

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
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 3つのスクリーンショット設定
SCREENSHOTS = {
    "ois_1m": {
        "url": "https://en.macromicro.me/series/6287/australia-overnight-indexed-swaps-1-month",
        "filename": "au_ois_1m.png",
        "label": "OIS 1M",
    },
    "ois_3m": {
        "url": "https://en.macromicro.me/series/6288/australia-overnight-indexed-swaps-3-month",
        "filename": "au_ois_3m.png",
        "label": "OIS 3M",
    },
    "ois_6m": {
        "url": "https://en.macromicro.me/series/6289/australia-overnight-indexed-swaps-6-month",
        "filename": "au_ois_6m.png",
        "label": "OIS 6M",
    },
}


class RbaOisScreenshotService:
    """RBA OIS Screenshot Service"""

    CACHE_KEY = "australia:rba_ois_screenshot:metadata"

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

            print(f"[RbaOIS] Accessing {url}")
            driver.get(url)

            print("[RbaOIS] Waiting for page to load...")
            time.sleep(5)

            # チャートコンテナが読み込まれるのを待つ
            try:
                wait = WebDriverWait(driver, 15)
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".mm-cc-bd .container.chart-theater.is-stat")
                    )
                )
                print("[RbaOIS] Chart container found")
                time.sleep(3)
            except Exception as e:
                print(f"[RbaOIS] Could not find chart container: {e}")

            # スクロールして表示
            try:
                chart_element = driver.find_element(
                    By.CSS_SELECTOR, ".mm-cc-bd .container.chart-theater.is-stat"
                )
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", chart_element
                )
                print("[RbaOIS] Scrolled to chart")
                time.sleep(2)
            except Exception as e:
                print(f"[RbaOIS] Could not scroll to chart: {e}")

            # 要素スクリーンショット
            try:
                chart_element = driver.find_element(
                    By.CSS_SELECTOR, ".mm-cc-bd .container.chart-theater.is-stat"
                )
                chart_element.screenshot(str(output_path))
                print(f"[RbaOIS] Screenshot saved to {output_path}")
                return True
            except Exception as e:
                print(f"[RbaOIS] Failed to capture element screenshot: {e}")
                print("[RbaOIS] Falling back to full page screenshot")
                driver.save_screenshot(str(output_path))
                return True

        except Exception as e:
            print(f"[RbaOIS] Error capturing screenshot from {url}: {e}")
            return False

        finally:
            if driver:
                driver.quit()
                print("[RbaOIS] Browser closed")

    def capture_all_screenshots(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Capture all OIS screenshots"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)
        results = {}

        for key, config in SCREENSHOTS.items():
            screenshot_path = CACHE_DIR / config["filename"]
            results[key] = {"success": False, "url": None, "cached": False}

            # キャッシュチェック（24時間）
            if not force_refresh and screenshot_path.exists():
                file_age = now.timestamp() - screenshot_path.stat().st_mtime
                if file_age < 86400:
                    results[key] = {
                        "success": True,
                        "url": f"/cache/australia/policy/{config['filename']}",
                        "cached": True,
                    }
                    print(f"[RbaOIS] Using cached {key} screenshot (age: {file_age/3600:.1f} hours)")
                    continue

            # スクリーンショット取得
            print(f"[RbaOIS] Capturing {config['label']} screenshot...")
            success = self._capture_screenshot(config["url"], screenshot_path)
            results[key] = {
                "success": success,
                "url": f"/cache/australia/policy/{config['filename']}" if success else None,
                "cached": False,
            }

        results["last_updated"] = now.isoformat()

        # メタデータをRedisに保存
        redis_client.set(
            self.CACHE_KEY,
            {
                "last_updated": now.isoformat(),
                **{f"{k}_exists": (CACHE_DIR / SCREENSHOTS[k]["filename"]).exists() for k in SCREENSHOTS},
            },
            expire=0,
        )

        return results

    def get_screenshot_urls(self) -> Dict[str, Any]:
        """Get URLs for cached screenshots"""
        result = {
            "screenshots": [],
            "last_updated": None,
        }

        for key, config in SCREENSHOTS.items():
            screenshot_path = CACHE_DIR / config["filename"]
            result["screenshots"].append({
                "key": key,
                "label": config["label"],
                "url": f"/cache/australia/policy/{config['filename']}" if screenshot_path.exists() else None,
                "exists": screenshot_path.exists(),
            })

        cached_meta = redis_client.get(self.CACHE_KEY)
        if cached_meta:
            result["last_updated"] = cached_meta.get("last_updated")
        else:
            # ファイルの更新日時を使用
            for config in SCREENSHOTS.values():
                p = CACHE_DIR / config["filename"]
                if p.exists():
                    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=JST)
                    result["last_updated"] = mtime.isoformat()
                    break

        return result

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        cached_meta = redis_client.get(self.CACHE_KEY)

        status = {
            "indicator": "RBA OIS Screenshots",
            "source": "MacroMicro",
            "cache_key": self.CACHE_KEY,
            "last_updated": cached_meta.get("last_updated") if cached_meta else None,
        }

        for key, config in SCREENSHOTS.items():
            status[f"{key}_exists"] = (CACHE_DIR / config["filename"]).exists()

        return status

    def invalidate_cache(self) -> bool:
        """Invalidate screenshot cache"""
        redis_client.delete(self.CACHE_KEY)
        return True


# シングルトンインスタンス
rba_ois_screenshot_service = RbaOisScreenshotService()

# パス参照用
SCREENSHOT_PATHS = {
    key: CACHE_DIR / config["filename"] for key, config in SCREENSHOTS.items()
}
