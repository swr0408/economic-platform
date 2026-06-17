"""Playwright (sync_api) ベースの BrowserRunner 実装。

これが「正」となる実装。新規 screenshot サービスや Selenium からの移行先は
すべてこの runner を使う。

Playwright を選ぶ理由:
    - ARM64 対応の公式 Chromium バイナリが配布されている
      (Selenium chromedriver は ARM64 公式バイナリが無く、Linux ディストリの
       chromium-driver パッケージに依存する必要がある)
    - 単一 API で chromium / firefox / webkit を切り替えられる
    - 公式 Docker イメージ (mcr.microsoft.com/playwright/python) が
      multi-arch (linux/amd64, linux/arm64) で提供されている
    - iframe / shadow DOM / waitFor* API が一級
    - 既存 services/usa/cme_fedwatch_screenshot_service.py で実績あり

このモジュールは playwright が import できない環境でも __init__ 自体は
失敗しない方針で書く (import を __enter__ に遅延させる)。理由:
    - Dockerfile.simple → Dockerfile.browser-worker への移行期に、
      backend コンテナから playwright を抜いた構成と両立させたい
    - テスト環境で playwright を入れずに contract test だけ走らせたい
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

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

logger = logging.getLogger(__name__)


class PlaywrightRunner(BrowserRunner):
    """Playwright sync_api ベースの実装。

    1 インスタンスが 1 ブラウザコンテキストを保持する。複数ページを同一
    コンテキストで撮りたい場合は同じ runner を使い回す (cookie/storage 共有)。
    """

    def __init__(
        self,
        config: Optional[BrowserConfig] = None,
        browser_type: str = "chromium",
    ) -> None:
        super().__init__(config)
        if browser_type not in ("chromium", "firefox", "webkit"):
            raise ValueError(f"unsupported browser_type: {browser_type}")
        self.browser_type: str = browser_type

        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    # ------------------------------------------------------------------ lifecycle

    def __enter__(self) -> "PlaywrightRunner":
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError as e:
            raise BrowserRunnerError(
                "playwright is not installed. Use Dockerfile.browser-worker "
                "or `pip install playwright && playwright install chromium`."
            ) from e

        try:
            self._playwright = sync_playwright().start()
            browser_launcher = getattr(self._playwright, self.browser_type)
            launch_args: list[str] = list(self.config.extra_browser_args)
            # コンテナ環境ではほぼ必須
            if "--no-sandbox" not in launch_args and os.environ.get("PLAYWRIGHT_NO_SANDBOX", "1") == "1":
                launch_args.append("--no-sandbox")
            if "--disable-dev-shm-usage" not in launch_args:
                launch_args.append("--disable-dev-shm-usage")

            self._browser = browser_launcher.launch(
                headless=self.config.headless,
                args=launch_args,
            )
            context_kwargs: dict[str, Any] = {
                "viewport": {
                    "width": self.config.viewport[0],
                    "height": self.config.viewport[1],
                },
            }
            if self.config.user_agent:
                context_kwargs["user_agent"] = self.config.user_agent
            if self.config.locale:
                context_kwargs["locale"] = self.config.locale
            if self.config.timezone_id:
                context_kwargs["timezone_id"] = self.config.timezone_id

            self._context = self._browser.new_context(**context_kwargs)
            self._context.set_default_navigation_timeout(self.config.default_navigation_timeout_ms)
            self._context.set_default_timeout(self.config.default_action_timeout_ms)
            return self
        except BrowserRunnerError:
            raise
        except Exception as e:
            self._safe_close()
            raise BrowserRunnerError(f"failed to start playwright: {e}") from e

    def __exit__(self, exc_type, exc, tb) -> None:
        self._safe_close()

    def _safe_close(self) -> None:
        for closer_name, closer in (
            ("context", self._context),
            ("browser", self._browser),
            ("playwright", self._playwright),
        ):
            if closer is None:
                continue
            try:
                if closer_name == "playwright":
                    closer.stop()
                else:
                    closer.close()
            except Exception as e:
                logger.warning(f"[playwright_runner] failed to close {closer_name}: {e}")
        self._context = None
        self._browser = None
        self._playwright = None

    # ------------------------------------------------------------------ public context

    @property
    def context(self) -> Any:
        """Playwright BrowserContext を公開する。

        multi-window フロー等、screenshot() / extract() では表現できない
        複雑な操作を行うサービス向け。run_custom_flow() 経由で使う。
        """
        self._ensure_started()
        return self._context

    # ------------------------------------------------------------------ helpers

    def _ensure_started(self) -> None:
        if self._context is None:
            raise BrowserRunnerError(
                "PlaywrightRunner must be used as a context manager (`with` block)"
            )

    def _new_page(self, viewport_override: Optional[tuple[int, int]]):
        page = self._context.new_page()  # type: ignore[union-attr]
        if viewport_override:
            page.set_viewport_size(
                {"width": viewport_override[0], "height": viewport_override[1]}
            )
        return page

    def _navigate_and_wait(
        self,
        page: Any,
        url: str,
        wait_for_load_state: str,
        pre_click_selectors: tuple[str, ...],
        wait_selector: Optional[str],
        wait_after_load_ms: int,
    ) -> None:
        from playwright.sync_api import (  # type: ignore
            TimeoutError as PlaywrightTimeoutError,
        )

        try:
            page.goto(url, wait_until=wait_for_load_state)
        except PlaywrightTimeoutError as e:
            raise BrowserTimeoutError(f"navigation timeout: {url}") from e
        except Exception as e:
            raise BrowserNavigationError(f"navigation failed for {url}: {e}") from e

        for sel in pre_click_selectors:
            try:
                page.click(sel, timeout=3_000)
            except Exception:
                logger.debug(f"[playwright_runner] pre_click skipped: {sel}")

        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, state="visible")
            except PlaywrightTimeoutError as e:
                raise BrowserTimeoutError(
                    f"wait_selector timeout: {wait_selector}"
                ) from e

        if wait_after_load_ms > 0:
            page.wait_for_timeout(wait_after_load_ms)

    # ------------------------------------------------------------------ screenshot

    def screenshot(self, request: ScreenshotRequest) -> ScreenshotResult:
        self._ensure_started()
        try:
            from playwright.sync_api import sync_playwright  # type: ignore  # noqa: F401
        except ImportError as e:
            raise BrowserRunnerError("playwright is not installed") from e

        page = self._new_page(request.viewport_override)
        try:
            self._navigate_and_wait(
                page,
                request.url,
                request.wait_for_load_state,
                request.pre_click_selectors,
                request.wait_selector,
                request.wait_after_load_ms,
            )

            # スクショ直前 JS フック (レイアウト調整等)。失敗は警告ログのみ。
            if request.pre_screenshot_js:
                try:
                    page.evaluate(request.pre_screenshot_js)
                except Exception as e:
                    logger.warning(
                        f"[playwright_runner] pre_screenshot_js failed: {e}"
                    )
                if request.wait_after_pre_js_ms > 0:
                    page.wait_for_timeout(request.wait_after_pre_js_ms)

            actual_url = page.url
            png_bytes: bytes
            if request.clip_selector:
                # wait_after_load_ms 経過後の一発 query では、描画が遅い
                # チャート (例: MacroMicro の一部ページ) で要素未出現のまま
                # 即失敗することがある。state="attached" で上限付きに待ってから
                # 取得する (visible 待ちは一部ページで timeout するため attached)。
                # タイムアウト時は従来どおり query→None で明確なエラーにする。
                try:
                    page.wait_for_selector(
                        request.clip_selector, state="attached", timeout=30_000
                    )
                except Exception:
                    pass
                element = page.query_selector(request.clip_selector)
                if element is None:
                    raise BrowserRunnerError(
                        f"clip_selector not found: {request.clip_selector}"
                    )
                if request.scroll_into_view:
                    try:
                        element.scroll_into_view_if_needed()
                    except Exception:
                        pass
                png_bytes = element.screenshot(type="png")
            else:
                png_bytes = page.screenshot(type="png", full_page=request.full_page)

            if request.output_path:
                os.makedirs(os.path.dirname(request.output_path), exist_ok=True)
                with open(request.output_path, "wb") as f:
                    f.write(png_bytes)
                return ScreenshotResult(
                    path=request.output_path,
                    data=None,
                    size_bytes=len(png_bytes),
                    url=actual_url,
                )
            return ScreenshotResult(
                path=None,
                data=png_bytes,
                size_bytes=len(png_bytes),
                url=actual_url,
            )
        finally:
            try:
                page.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ extract

    def extract(self, request: ExtractRequest) -> ExtractResult:
        self._ensure_started()
        try:
            from playwright.sync_api import sync_playwright  # type: ignore  # noqa: F401
        except ImportError as e:
            raise BrowserRunnerError("playwright is not installed") from e

        page = self._new_page(request.viewport_override)
        try:
            self._navigate_and_wait(
                page,
                request.url,
                request.wait_for_load_state,
                request.pre_click_selectors,
                request.wait_selector,
                request.wait_after_load_ms,
            )

            texts: dict[str, list[str]] = {}
            for sel in request.text_selectors:
                try:
                    elements = page.query_selector_all(sel)
                    texts[sel] = [
                        (e.inner_text() or "").strip() for e in elements
                    ]
                except Exception as e:
                    logger.warning(
                        f"[playwright_runner] text_selector failed: {sel}: {e}"
                    )
                    texts[sel] = []

            html: dict[str, list[str]] = {}
            for sel in request.html_selectors:
                try:
                    elements = page.query_selector_all(sel)
                    html[sel] = [
                        (e.evaluate("el => el.outerHTML") or "") for e in elements
                    ]
                except Exception as e:
                    logger.warning(
                        f"[playwright_runner] html_selector failed: {sel}: {e}"
                    )
                    html[sel] = []

            evaluated: object = None
            if request.evaluate_js:
                try:
                    evaluated = page.evaluate(request.evaluate_js)
                except Exception as e:
                    raise BrowserRunnerError(
                        f"evaluate_js failed: {e}"
                    ) from e

            return ExtractResult(
                url=page.url,
                texts=texts,
                html=html,
                evaluated=evaluated,
            )
        finally:
            try:
                page.close()
            except Exception:
                pass
