"""
backend.services.browser
========================

ブラウザ自動化 (Playwright / Selenium) を抽象化するパッケージ。

目的:
    - 既存の screenshot サービス群 (中国李克強指数, RBA OIS, CME FedWatch ...)
      が直接 Playwright/Selenium API を叩いている現状を、徐々に
      `BrowserRunner` インターフェース経由に統一する。
    - OCI Always Free (ARM64) など、Selenium chromedriver が公式バイナリを
      持たない環境への移行を可能にする。
    - 将来的に `browser-worker` コンテナへ分離する際の境界面を先に確定する。

使い方 (高レベル):

    from backend.services.browser import take_screenshot, ScreenshotRequest

    result = take_screenshot(ScreenshotRequest(
        url="https://example.com",
        output_path="/app/screenshots/example.png",
        wait_selector="div.chart-ready",
        viewport=(1920, 1080),
    ))

使い方 (低レベル, runner を直接使う):

    from backend.services.browser import get_default_runner

    with get_default_runner() as runner:
        runner.screenshot(request)

設計方針:
    - **既存サービスは変更しない**。新規 / 移行は段階的に行う。
    - Playwright を「正」、Selenium は廃止予定 (skeleton のみ提供)。
    - 同期 API のみを提供する (既存 service が同期前提のため)。
      非同期版が必要な箇所は当面ローカルで `asyncio.run` するか、Playwright の
      sync_api を使う。
    - 並列実行は `concurrency.browser_semaphore` で 1 ホスト 2 並列に制限する。
"""
from __future__ import annotations

from .exceptions import (
    BrowserNavigationError,
    BrowserRunnerError,
    BrowserTimeoutError,
)
from .runner import (
    BrowserConfig,
    BrowserRunner,
    ExtractRequest,
    ExtractResult,
    ScreenshotRequest,
    ScreenshotResult,
)
from .screenshot_helper import (
    extract_page,
    get_default_runner,
    take_screenshot,
    take_screenshot_with_retry,
)

__all__ = [
    "BrowserConfig",
    "BrowserNavigationError",
    "BrowserRunner",
    "BrowserRunnerError",
    "BrowserTimeoutError",
    "ExtractRequest",
    "ExtractResult",
    "ScreenshotRequest",
    "ScreenshotResult",
    "extract_page",
    "get_default_runner",
    "take_screenshot",
    "take_screenshot_with_retry",
]
