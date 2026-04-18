"""
Fed Rate Cuts Expectation Screenshot Service
Captures screenshots from MacroMicro charts via PlaywrightRunner

URLs (2026年):
- 年末金利予想: https://en.macromicro.me/series/78278/us-fed-year-end-interest-rate-expectation-2026
- 利下げ回数: https://en.macromicro.me/series/78284/us-fed-interest-rate-cuts-expectation-2026

Target: main tab > class="mm-cc-bd" > class="container chart-theater is-stat"
"""
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.browser import (
    BrowserConfig,
    BrowserRunnerError,
    ScreenshotRequest,
    get_default_runner,
)
from services.browser.concurrency import browser_semaphore
from services.browser.stale_while_revalidate import background_revalidate

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

YEAREND_SCREENSHOT_FILENAME = "fed_yearend_rate_expectations.png"
RATE_CUTS_SCREENSHOT_FILENAME = "fed_rate_cuts_expectations.png"

YEAREND_SCREENSHOT_PATH = CACHE_DIR / YEAREND_SCREENSHOT_FILENAME
RATE_CUTS_SCREENSHOT_PATH = CACHE_DIR / RATE_CUTS_SCREENSHOT_FILENAME

YEAREND_URL = "https://en.macromicro.me/series/78278/us-fed-year-end-interest-rate-expectation-2026"
RATE_CUTS_URL = "https://en.macromicro.me/series/78284/us-fed-interest-rate-cuts-expectation-2026"


class FedRateCutsScreenshotService:
    """Fed Rate Cuts Expectation Screenshot Service"""

    CACHE_KEY = "usa:fed_rate_cuts_screenshot:metadata"
    TARGET_SELECTOR = ".mm-cc-bd .container.chart-theater.is-stat"

    def __init__(self):
        pass

    def _build_request(self, url: str, output_path: Path) -> ScreenshotRequest:
        return ScreenshotRequest(
            url=url,
            output_path=str(output_path),
            wait_for_load_state="domcontentloaded",
            wait_after_load_ms=10_000,
            clip_selector=self.TARGET_SELECTOR,
            scroll_into_view=True,
            viewport_override=(1920, 1400),
        )

    def _build_config(self) -> BrowserConfig:
        return BrowserConfig(
            viewport=(1920, 1400),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

    def _capture_fresh(self) -> Dict[str, Any]:
        return self.capture_all_screenshots(force_refresh=True)

    def capture_all_screenshots(self, force_refresh: bool = False) -> Dict[str, Any]:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)
        results: Dict[str, Any] = {
            "yearend": {"success": False, "url": None, "cached": False},
            "rate_cuts": {"success": False, "url": None, "cached": False},
            "last_updated": None,
        }

        items = [
            ("yearend", YEAREND_URL, YEAREND_SCREENSHOT_PATH, YEAREND_SCREENSHOT_FILENAME),
            ("rate_cuts", RATE_CUTS_URL, RATE_CUTS_SCREENSHOT_PATH, RATE_CUTS_SCREENSHOT_FILENAME),
        ]

        to_capture: list[tuple[str, str, Path, str]] = []
        for key, url, path, filename in items:
            if not force_refresh and path.exists():
                file_age = now.timestamp() - path.stat().st_mtime
                if file_age < 86400:
                    results[key] = {
                        "success": True,
                        "url": f"/cache/usa/policy/{filename}",
                        "cached": True,
                    }
                    logger.info(
                        f"[FedRateCuts] Using cached {key} screenshot "
                        f"(age: {file_age/3600:.1f} hours)"
                    )
                    continue
            to_capture.append((key, url, path, filename))

        if not to_capture:
            cached_meta = redis_client.get(self.CACHE_KEY)
            results["last_updated"] = (
                cached_meta.get("last_updated") if cached_meta else now.isoformat()
            )
            return results

        all_files_exist = all(path.exists() for _, _, path, _ in to_capture)
        if all_files_exist and not force_refresh:
            for key, url, path, filename in to_capture:
                results[key] = {
                    "success": True,
                    "url": f"/cache/usa/policy/{filename}",
                    "cached": True,
                }
            cached_meta = redis_client.get(self.CACHE_KEY)
            results["last_updated"] = (
                cached_meta.get("last_updated") if cached_meta else now.isoformat()
            )
            results["revalidating"] = True
            background_revalidate(
                f"swr:{self.CACHE_KEY}",
                lambda: self._capture_fresh(),
            )
            return results

        for idx, (key, url, path, filename) in enumerate(to_capture):
            if idx > 0:
                time.sleep(10)
            try:
                with browser_semaphore:
                    with get_default_runner(config=self._build_config()) as runner:
                        logger.info(f"[FedRateCuts] Capturing {key}...")
                        cap_result = runner.screenshot(self._build_request(url, path))

                if path.exists() and path.stat().st_size < 30_000:
                    logger.warning(
                        f"[FedRateCuts] {key}: file too small "
                        f"({path.stat().st_size} bytes), likely Cloudflare page"
                    )
                    results[key] = {
                        "success": False,
                        "url": None,
                        "cached": False,
                    }
                    continue

                logger.info(
                    f"[FedRateCuts] saved {key}: "
                    f"{cap_result.path} ({cap_result.size_bytes} bytes)"
                )
                results[key] = {
                    "success": True,
                    "url": f"/cache/usa/policy/{filename}",
                    "cached": False,
                }
            except BrowserRunnerError as e:
                logger.error(f"[FedRateCuts] {key} capture failed: {e}")
                results[key] = {
                    "success": False,
                    "url": None,
                    "cached": False,
                }

        results["last_updated"] = now.isoformat()

        redis_client.set(self.CACHE_KEY, {
            "last_updated": now.isoformat(),
            "yearend_exists": YEAREND_SCREENSHOT_PATH.exists(),
            "rate_cuts_exists": RATE_CUTS_SCREENSHOT_PATH.exists()
        }, expire=0)

        return results

    def get_screenshot_urls(self) -> Dict[str, Any]:
        result = {
            "yearend_url": None,
            "rate_cuts_url": None,
            "last_updated": None
        }

        if YEAREND_SCREENSHOT_PATH.exists():
            result["yearend_url"] = f"/cache/usa/policy/{YEAREND_SCREENSHOT_FILENAME}"

        if RATE_CUTS_SCREENSHOT_PATH.exists():
            result["rate_cuts_url"] = f"/cache/usa/policy/{RATE_CUTS_SCREENSHOT_FILENAME}"

        cached_meta = redis_client.get(self.CACHE_KEY)
        if cached_meta:
            result["last_updated"] = cached_meta.get("last_updated")
        elif YEAREND_SCREENSHOT_PATH.exists():
            mtime = datetime.fromtimestamp(YEAREND_SCREENSHOT_PATH.stat().st_mtime, tz=JST)
            result["last_updated"] = mtime.isoformat()

        return result

    def get_cache_status(self) -> Dict[str, Any]:
        cached_meta = redis_client.get(self.CACHE_KEY)
        return {
            "indicator": "Fed Rate Cuts Expectations Screenshots",
            "source": "MacroMicro",
            "cache_key": self.CACHE_KEY,
            "yearend_exists": YEAREND_SCREENSHOT_PATH.exists(),
            "rate_cuts_exists": RATE_CUTS_SCREENSHOT_PATH.exists(),
            "last_updated": cached_meta.get("last_updated") if cached_meta else None
        }

    def invalidate_cache(self) -> bool:
        redis_client.delete(self.CACHE_KEY)
        return True


fed_rate_cuts_screenshot_service = FedRateCutsScreenshotService()
