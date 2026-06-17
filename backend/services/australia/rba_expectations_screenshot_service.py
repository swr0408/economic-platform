"""
RBA 利上げ・利下げ期待 Screenshot Service
Captures screenshots from MacroMicro charts via PlaywrightRunner

2枚のスクリーンショット:
- Year-End Rate Expectation: https://en.macromicro.me/series/78282/australia-rba-year-end-interest-rate-expectation-2026
- Rate Cuts Expectation: https://en.macromicro.me/series/78288/australia-rba-interest-rate-cuts-expectation-2026

Target CSS: .mm-cc-bd .container.chart-theater.is-stat

[移行ノート]
このサービスは backend.services.browser.PlaywrightRunner 経由に統一済み
(ARM64 / OCI 対応)。以前の Selenium / webdriver_manager / chromium-driver
依存はすべて削除。複数 URL を 1 ブラウザで撮るため、`get_default_runner`
+ `browser_semaphore` を直接使うパターン。public API
(capture_all_screenshots / get_screenshot_urls / get_cache_status /
invalidate_cache) は完全互換。
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

# 2つのスクリーンショット設定
SCREENSHOTS = {
    "year_end_rate": {
        "url": "https://en.macromicro.me/series/78282/australia-rba-year-end-interest-rate-expectation-2026",
        "filename": "au_rba_year_end_rate_expectation.png",
        "label": "Year-End Rate Expectation",
    },
    "rate_cuts": {
        "url": "https://en.macromicro.me/series/78288/australia-rba-interest-rate-cuts-expectation-2026",
        "filename": "au_rba_rate_cuts_expectation.png",
        "label": "Rate Cuts Expectation",
    },
}


class RbaExpectationsScreenshotService:
    """RBA Expectations Screenshot Service"""

    CACHE_KEY = "australia:rba_expectations_screenshot:metadata"

    # MacroMicro 共通のチャートコンテナ
    TARGET_SELECTOR = ".mm-cc-bd .container.chart-theater.is-stat"

    def __init__(self):
        pass

    def _build_request(self, url: str, output_path: Path) -> ScreenshotRequest:
        # MacroMicro rate_cuts ページは "visible" 判定が timeout することがあるため、
        # wait_selector を省略し wait_after_load_ms (15s) でチャート描画を待機。
        return ScreenshotRequest(
            url=url,
            output_path=str(output_path),
            wait_for_load_state="domcontentloaded",
            wait_after_load_ms=25_000,
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
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            default_navigation_timeout_ms=120_000,
            default_action_timeout_ms=60_000,
        )

    def capture_all_screenshots(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Capture all expectations screenshots.

        MacroMicro の連続ロード抑制を避けるため 1 枚ごとに新しいブラウザを
        起動する。プロセス共有セマフォ (`browser_semaphore`) は 1 度だけ取得し、
        その中で順次撮影する。
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)
        results: Dict[str, Any] = {}

        # まず、撮影が必要なものだけ抽出 (キャッシュ済みは即決)
        to_capture: list[tuple[str, dict, Path]] = []
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
                    logger.info(
                        f"[RbaExpectations] Using cached {key} screenshot "
                        f"(age: {file_age/3600:.1f} hours)"
                    )
                    continue
            to_capture.append((key, config, screenshot_path))

        # SWR: all files exist (but stale) → return stale URLs, update in background
        # force_refresh=True は明示的な再取得要求なので SWR をスキップし同期撮影する。
        # （SWR を通すと all_files_exist=True で永久に stale を返し、background も
        #  同一 task_key で再度 SWR に入り実撮影されない no-op ループになる）
        if to_capture and not force_refresh:
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

        # MacroMicro は同一ブラウザで複数チャートを連続ロードすると 2 枚目以降が
        # 描画されない (highcharts 未生成 → clip_selector not found) ため、
        # 1 枚ごとに新しいブラウザを起動して各撮影を「初回ロード」にする。
        # browser_semaphore は 1 度だけ取得し、その中で順次起動する。
        if to_capture:
            with browser_semaphore:
                for key, config, screenshot_path in to_capture:
                    try:
                        logger.info(
                            f"[RbaExpectations] Capturing {config['label']}..."
                        )
                        with get_default_runner(config=self._build_config()) as runner:
                            result = runner.screenshot(
                                self._build_request(config["url"], screenshot_path)
                            )
                        logger.info(
                            f"[RbaExpectations] saved {key}: "
                            f"{result.path} ({result.size_bytes} bytes)"
                        )
                        results[key] = {
                            "success": True,
                            "url": f"/cache/australia/policy/{config['filename']}",
                            "cached": False,
                        }
                    except BrowserRunnerError as e:
                        logger.error(
                            f"[RbaExpectations] {key} capture failed: {e}"
                        )
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
            "indicator": "RBA Expectations Screenshots",
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
rba_expectations_screenshot_service = RbaExpectationsScreenshotService()

# パス参照用
SCREENSHOT_PATHS = {
    key: CACHE_DIR / config["filename"] for key, config in SCREENSHOTS.items()
}
