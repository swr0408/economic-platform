"""screenshot / extract 取得の高レベルファサード。

既存サービスがコピペで使えるよう、1 関数呼び出しで完結する API を提供する。

    from backend.services.browser import take_screenshot, ScreenshotRequest

    result = take_screenshot(ScreenshotRequest(
        url="https://truflation.com/marketplace/us-inflation-rate",
        output_path="/app/screenshots/truflation_us_cpi_1y.png",
        wait_selector="canvas",
        wait_after_load_ms=2000,
        viewport_override=(1440, 900),
    ))

このファサードは:
    1. デフォルト runner (= PlaywrightRunner) を起動
    2. プロセス共有セマフォ (concurrency.browser_semaphore) を取得
    3. screenshot 1 枚を撮って結果を返す
    4. 確実に runner を閉じる

セマフォ取得をここでやることで、runner 単体テストはセマフォ無しで素直に
書ける (= runner はステートレスに保たれる)。

複数枚のスクショを 1 ブラウザで撮りたい場合は `get_default_runner()` を
使って自前で context を管理する。
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from .concurrency import browser_semaphore
from .exceptions import BrowserNavigationError, BrowserRunnerError, BrowserTimeoutError
from .playwright_runner import PlaywrightRunner
from .runner import (
    BrowserConfig,
    BrowserRunner,
    ExtractRequest,
    ExtractResult,
    ScreenshotRequest,
    ScreenshotResult,
)

logger = logging.getLogger(__name__)


def get_default_runner(
    config: Optional[BrowserConfig] = None,
    browser_type: str = "chromium",
) -> BrowserRunner:
    """既定の BrowserRunner (現状 = PlaywrightRunner) を返す。

    返されたインスタンスは context manager として使うこと:

        with get_default_runner() as runner:
            runner.screenshot(req1)
            runner.screenshot(req2)

    将来 runner 実装を切り替える際は、この 1 関数だけ書き換えれば全呼び出し
    元に伝播する。
    """
    return PlaywrightRunner(config=config, browser_type=browser_type)


def take_screenshot(
    request: ScreenshotRequest,
    config: Optional[BrowserConfig] = None,
    browser_type: str = "chromium",
) -> ScreenshotResult:
    """1 リクエストだけスクショを取得する高レベルヘルパー。

    並列実行数は ``concurrency.browser_semaphore`` で抑制される
    (デフォルト 2 並列)。
    """
    with browser_semaphore:
        with get_default_runner(config=config, browser_type=browser_type) as runner:
            return runner.screenshot(request)


def extract_page(
    request: ExtractRequest,
    config: Optional[BrowserConfig] = None,
    browser_type: str = "chromium",
) -> ExtractResult:
    """1 リクエストだけ DOM 抽出する高レベルヘルパー。

    `take_screenshot` のデータスクレイピング版。並列実行数は同じセマフォで制御。
    """
    with browser_semaphore:
        with get_default_runner(config=config, browser_type=browser_type) as runner:
            return runner.extract(request)


# 一時的なエラー (ネットワーク / タイムアウト) でリトライ可能な例外型
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    BrowserTimeoutError,
    BrowserNavigationError,
)


def take_screenshot_with_retry(
    request: ScreenshotRequest,
    config: Optional[BrowserConfig] = None,
    browser_type: str = "chromium",
    max_attempts: int = 3,
    initial_backoff_seconds: float = 2.0,
    backoff_multiplier: float = 2.0,
) -> ScreenshotResult:
    """`take_screenshot` をリトライ付きで実行する。

    `BrowserTimeoutError` / `BrowserNavigationError` のみリトライする。
    `BrowserRunnerError` (設定ミス等) はリトライしない。

    Args:
        request: スクショリクエスト
        config: BrowserConfig
        browser_type: "chromium" | "firefox" | "webkit"
        max_attempts: 最大試行回数 (1 = リトライ無し)
        initial_backoff_seconds: 初回リトライまでの待機 (秒)
        backoff_multiplier: 指数バックオフの倍率

    Raises:
        BrowserRunnerError: 全試行失敗時、最後の例外を再 raise
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_error: Optional[BrowserRunnerError] = None
    backoff = initial_backoff_seconds

    for attempt in range(1, max_attempts + 1):
        try:
            return take_screenshot(request, config=config, browser_type=browser_type)
        except _RETRYABLE_EXCEPTIONS as e:
            last_error = e
            if attempt >= max_attempts:
                logger.error(
                    f"[take_screenshot_with_retry] all {max_attempts} attempts failed "
                    f"for {request.url}: {e}"
                )
                raise
            logger.warning(
                f"[take_screenshot_with_retry] attempt {attempt}/{max_attempts} "
                f"failed for {request.url}: {e}; retrying in {backoff:.1f}s"
            )
            time.sleep(backoff)
            backoff *= backoff_multiplier
        except BrowserRunnerError:
            # 設定エラー等はリトライしても無駄
            raise

    # ここには到達しないはずだが型のため
    assert last_error is not None
    raise last_error
