"""
ECB Rate Cuts Expectation Screenshot Service
Captures screenshots from MacroMicro charts via PlaywrightRunner

URLs (2026年):
- 年末金利予想: https://en.macromicro.me/series/78279/euro-area-ecb-year-end-interest-rate-expectation-2026
- 利上げ・利下げ回数: https://en.macromicro.me/series/78285/euro-area-ecb-interest-rate-cuts-expectation-2026

Target: main tab > class="mm-cc-bd" > class="container chart-theater is-stat"

[移行ノート]
このサービスは backend.services.browser.PlaywrightRunner 経由に統一済み
(ARM64 / OCI 対応)。以前の Selenium / webdriver_manager / chromium-driver
依存はすべて削除。2 URL を 1 ブラウザで連続撮影するため
`get_default_runner` + `browser_semaphore` を直接使うパターン。public API
(capture_all_screenshots / get_screenshot_urls / get_cache_status /
invalidate_cache) は完全互換。
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

# キャッシュディレクトリの設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "monetary_policy"
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

    # MacroMicro 共通のチャートコンテナ
    TARGET_SELECTOR = ".mm-cc-bd .container.chart-theater.is-stat"

    def __init__(self):
        pass

    def _build_request(self, url: str, output_path: Path) -> ScreenshotRequest:
        # MacroMicro は Cloudflare チャレンジを挟むことがあるため
        # wait_selector は使わず wait_after_load_ms でチャート描画を待つ。
        # clip_selector はチャート部分の切り出しに使用。
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
        """SWR バックグラウンド用: 常に Playwright で撮影する（SWR 再帰なし）"""
        return self.capture_all_screenshots(force_refresh=True)

    def capture_all_screenshots(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Capture all ECB rate expectation screenshots.

        2 枚を 1 ブラウザで連続撮影 (起動コスト削減)。プロセス共有セマフォ
        (`browser_semaphore`) を 1 度だけ取得する。
        """
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

        # キャッシュ済みは即決、撮影が必要なものを抽出
        to_capture: list[tuple[str, str, Path, str]] = []
        for key, url, path, filename in items:
            if not force_refresh and path.exists():
                file_age = now.timestamp() - path.stat().st_mtime
                if file_age < 86400:
                    results[key] = {
                        "success": True,
                        "url": f"/cache/eurozone/monetary_policy/{filename}",
                        "cached": True,
                    }
                    logger.info(
                        f"[ECBRateCuts] Using cached {key} screenshot "
                        f"(age: {file_age/3600:.1f} hours)"
                    )
                    continue
            to_capture.append((key, url, path, filename))

        # 両方キャッシュ済みなら即返す
        if not to_capture:
            cached_meta = redis_client.get(self.CACHE_KEY)
            results["last_updated"] = (
                cached_meta.get("last_updated") if cached_meta else now.isoformat()
            )
            return results

        # SWR: all files exist (but stale) AND not force_refresh
        # → return stale URLs immediately, update in background
        # force_refresh=True の場合は SWR をスキップして直接キャプチャする
        all_files_exist = all(path.exists() for _, _, path, _ in to_capture)
        if all_files_exist and not force_refresh:
            for key, url, path, filename in to_capture:
                results[key] = {
                    "success": True,
                    "url": f"/cache/eurozone/monetary_policy/{filename}",
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

        # Cloudflare 対策: URL ごとに別ブラウザインスタンスで撮影し、
        # 間にディレイを入れる
        for idx, (key, url, path, filename) in enumerate(to_capture):
            if idx > 0:
                time.sleep(10)  # Cloudflare rate-limit 回避
            try:
                with browser_semaphore:
                    with get_default_runner(config=self._build_config()) as runner:
                        logger.info(f"[ECBRateCuts] Capturing {key}...")
                        cap_result = runner.screenshot(self._build_request(url, path))

                # Cloudflare チャレンジページ検出（ファイルサイズが小さすぎる
                # or 大きすぎる場合は正常なチャートではない可能性）
                if path.exists() and path.stat().st_size < 30_000:
                    logger.warning(
                        f"[ECBRateCuts] {key}: file too small "
                        f"({path.stat().st_size} bytes), likely Cloudflare page"
                    )
                    results[key] = {
                        "success": False,
                        "url": None,
                        "cached": False,
                    }
                    continue

                logger.info(
                    f"[ECBRateCuts] saved {key}: "
                    f"{cap_result.path} ({cap_result.size_bytes} bytes)"
                )
                results[key] = {
                    "success": True,
                    "url": f"/cache/eurozone/monetary_policy/{filename}",
                    "cached": False,
                }
            except BrowserRunnerError as e:
                logger.error(f"[ECBRateCuts] {key} capture failed: {e}")
                results[key] = {
                    "success": False,
                    "url": None,
                    "cached": False,
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
