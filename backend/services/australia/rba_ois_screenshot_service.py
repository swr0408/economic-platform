"""
RBA OIS Screenshot Service
Captures screenshots from MacroMicro charts via PlaywrightRunner

3枚のスクリーンショット:
- 1M OIS: https://en.macromicro.me/series/6287/australia-overnight-indexed-swaps-1-month
- 3M OIS: https://en.macromicro.me/series/6288/australia-overnight-indexed-swaps-3-month
- 6M OIS: https://en.macromicro.me/series/6289/australia-overnight-indexed-swaps-6-month

Target CSS: .mm-cc-bd .container.chart-theater.is-stat

[移行ノート]
このサービスは backend.services.browser.PlaywrightRunner 経由に統一済み
(ARM64 / OCI 対応)。以前の Selenium / webdriver_manager / chromium-driver
依存はすべて削除。3 URL を 1 ブラウザで連続撮影するため
`get_default_runner` + `browser_semaphore` を直接使うパターン。
public API (capture_all_screenshots / get_screenshot_urls /
get_cache_status / invalidate_cache) は完全互換。
"""
import logging
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

    # MacroMicro 共通のチャートコンテナ
    TARGET_SELECTOR = ".mm-cc-bd .container.chart-theater.is-stat"

    def __init__(self):
        pass

    def _build_request(self, url: str, output_path: Path) -> ScreenshotRequest:
        return ScreenshotRequest(
            url=url,
            output_path=str(output_path),
            wait_selector=self.TARGET_SELECTOR,
            wait_for_load_state="networkidle",
            wait_after_load_ms=5_000,
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

    def capture_all_screenshots(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Capture all OIS screenshots.

        3 枚を 1 ブラウザで連続撮影 (起動コスト削減)。プロセス共有セマフォ
        (`browser_semaphore`) を 1 度だけ取得する。
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)
        results: Dict[str, Any] = {}

        # キャッシュ済みは即決、撮影が必要なものだけ抽出
        to_capture: list[tuple[str, dict, Path]] = []
        for key, config in SCREENSHOTS.items():
            screenshot_path = CACHE_DIR / config["filename"]
            results[key] = {"success": False, "url": None, "cached": False}

            if not force_refresh and screenshot_path.exists():
                file_age = now.timestamp() - screenshot_path.stat().st_mtime
                if file_age < 86400:
                    results[key] = {
                        "success": True,
                        "url": f"/cache/australia/policy/{config['filename']}",
                        "cached": True,
                    }
                    logger.info(
                        f"[RbaOIS] Using cached {key} screenshot "
                        f"(age: {file_age/3600:.1f} hours)"
                    )
                    continue
            to_capture.append((key, config, screenshot_path))

        # SWR: all files exist (but stale) → return stale URLs, update in background
        if to_capture:
            all_files_exist = all(sp.exists() for _, _, sp in to_capture)
            if all_files_exist:
                for key, config, screenshot_path in to_capture:
                    results[key] = {
                        "success": True,
                        "url": f"/cache/australia/policy/{config['filename']}",
                        "cached": True,
                    }
                cached_meta = redis_client.get(self.CACHE_KEY)
                results["last_updated"] = (
                    cached_meta.get("last_updated") if cached_meta else now.isoformat()
                )
                results["revalidating"] = True
                background_revalidate(
                    f"swr:{self.CACHE_KEY}",
                    lambda: self.capture_all_screenshots(force_refresh=True),
                )
                return results

        # 1 ブラウザで複数枚連続撮影
        if to_capture:
            try:
                with browser_semaphore:
                    with get_default_runner(config=self._build_config()) as runner:
                        for key, config, screenshot_path in to_capture:
                            try:
                                logger.info(
                                    f"[RbaOIS] Capturing {config['label']}..."
                                )
                                result = runner.screenshot(
                                    self._build_request(config["url"], screenshot_path)
                                )
                                logger.info(
                                    f"[RbaOIS] saved {key}: "
                                    f"{result.path} ({result.size_bytes} bytes)"
                                )
                                results[key] = {
                                    "success": True,
                                    "url": f"/cache/australia/policy/{config['filename']}",
                                    "cached": False,
                                }
                            except BrowserRunnerError as e:
                                logger.error(
                                    f"[RbaOIS] {key} capture failed: {e}"
                                )
                                results[key] = {
                                    "success": False,
                                    "url": None,
                                    "cached": False,
                                }
            except BrowserRunnerError as e:
                logger.error(f"[RbaOIS] runner setup failed: {e}")
                for key, config, _ in to_capture:
                    results[key] = {
                        "success": False,
                        "url": None,
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
