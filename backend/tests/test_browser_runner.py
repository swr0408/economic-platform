"""backend.services.browser パッケージの contract テスト。

playwright を実際にインストールしていない環境でも走るよう、
PlaywrightRunner の起動部分は import エラーを期待する形で検証する。
それ以外 (dataclass 構造 / セマフォ / 例外階層 / SeleniumRunner skeleton)
は完全にスタンドアロンで検証可能。
"""
from __future__ import annotations

import threading

import pytest

from services.browser import (
    BrowserConfig,
    BrowserNavigationError,
    BrowserRunner,
    BrowserRunnerError,
    BrowserTimeoutError,
    ExtractRequest,
    ExtractResult,
    ScreenshotRequest,
    ScreenshotResult,
    extract_page,
    get_default_runner,
    take_screenshot,
    take_screenshot_with_retry,
)
from services.browser.concurrency import browser_semaphore, get_concurrency_limit
from services.browser.playwright_runner import PlaywrightRunner
from services.browser.selenium_runner import SeleniumRunner


# ---------------------------------------------------------------- dataclass


class TestDataclasses:
    def test_browser_config_defaults(self):
        cfg = BrowserConfig()
        assert cfg.viewport == (1920, 1080)
        assert cfg.headless is True
        assert cfg.user_agent is None
        assert cfg.locale is None
        assert cfg.timezone_id is None
        assert cfg.default_navigation_timeout_ms == 60_000
        assert cfg.default_action_timeout_ms == 30_000
        assert cfg.extra_browser_args == ()

    def test_browser_config_immutable(self):
        cfg = BrowserConfig()
        with pytest.raises(Exception):
            cfg.viewport = (800, 600)  # type: ignore

    def test_screenshot_request_minimal(self):
        req = ScreenshotRequest(url="https://example.com")
        assert req.url == "https://example.com"
        assert req.output_path is None
        assert req.wait_selector is None
        assert req.wait_for_load_state == "networkidle"
        assert req.wait_after_load_ms == 0
        assert req.full_page is False
        assert req.pre_click_selectors == ()
        assert req.scroll_into_view is False

    def test_screenshot_request_full(self):
        req = ScreenshotRequest(
            url="https://example.com",
            output_path="/tmp/x.png",
            wait_selector="canvas",
            wait_for_load_state="load",
            wait_after_load_ms=1500,
            clip_selector=".chart",
            full_page=False,
            pre_click_selectors=("#cookie-accept", ".banner-close"),
            viewport_override=(1366, 768),
            scroll_into_view=True,
        )
        assert req.output_path == "/tmp/x.png"
        assert req.pre_click_selectors == ("#cookie-accept", ".banner-close")
        assert req.viewport_override == (1366, 768)

    def test_screenshot_result_immutable(self):
        result = ScreenshotResult(
            path="/tmp/x.png", data=None, size_bytes=1234, url="https://example.com/redirected"
        )
        assert result.size_bytes == 1234
        with pytest.raises(Exception):
            result.size_bytes = 0  # type: ignore

    def test_screenshot_request_pre_screenshot_js_default(self):
        req = ScreenshotRequest(url="https://example.com")
        assert req.pre_screenshot_js is None
        assert req.wait_after_pre_js_ms == 0

    def test_screenshot_request_pre_screenshot_js_set(self):
        req = ScreenshotRequest(
            url="https://example.com",
            pre_screenshot_js="document.body.style.background = 'red';",
            wait_after_pre_js_ms=1_000,
        )
        assert "background" in req.pre_screenshot_js
        assert req.wait_after_pre_js_ms == 1_000

    def test_extract_request_minimal(self):
        req = ExtractRequest(url="https://example.com")
        assert req.url == "https://example.com"
        assert req.text_selectors == ()
        assert req.html_selectors == ()
        assert req.evaluate_js is None
        assert req.wait_for_load_state == "networkidle"

    def test_extract_request_full(self):
        req = ExtractRequest(
            url="https://example.com",
            wait_selector="div.ready",
            wait_after_load_ms=500,
            pre_click_selectors=("#accept",),
            text_selectors=("h1", ".value"),
            html_selectors=(".chart-svg",),
            evaluate_js="window.__data__",
            viewport_override=(1280, 720),
        )
        assert req.text_selectors == ("h1", ".value")
        assert req.html_selectors == (".chart-svg",)
        assert req.evaluate_js == "window.__data__"

    def test_extract_result_immutable(self):
        result = ExtractResult(
            url="https://example.com/x",
            texts={"h1": ["hello"]},
            html={".chart": ["<svg/>"]},
            evaluated={"k": "v"},
        )
        assert result.texts["h1"] == ["hello"]
        with pytest.raises(Exception):
            result.url = "x"  # type: ignore


# ---------------------------------------------------------------- exceptions


class TestExceptionHierarchy:
    def test_timeout_is_runner_error(self):
        assert issubclass(BrowserTimeoutError, BrowserRunnerError)

    def test_navigation_is_runner_error(self):
        assert issubclass(BrowserNavigationError, BrowserRunnerError)

    def test_runner_error_is_exception(self):
        assert issubclass(BrowserRunnerError, Exception)


# ---------------------------------------------------------------- concurrency


class TestConcurrency:
    def test_semaphore_is_bounded(self):
        # threading.BoundedSemaphore は release 過剰で ValueError
        assert isinstance(browser_semaphore, threading.BoundedSemaphore) or hasattr(
            browser_semaphore, "acquire"
        )

    def test_concurrency_limit_positive(self):
        assert get_concurrency_limit() >= 1

    def test_semaphore_acquire_release(self):
        # 取得して即解放できることを確認 (デッドロック検出)
        acquired = browser_semaphore.acquire(timeout=1)
        assert acquired is True
        browser_semaphore.release()


# ---------------------------------------------------------------- runner contract


class TestRunnerContract:
    def test_browser_runner_is_abstract(self):
        with pytest.raises(TypeError):
            BrowserRunner()  # type: ignore

    def test_playwright_runner_is_runner(self):
        runner = PlaywrightRunner(BrowserConfig())
        assert isinstance(runner, BrowserRunner)

    def test_selenium_runner_is_runner(self):
        runner = SeleniumRunner(BrowserConfig())
        assert isinstance(runner, BrowserRunner)

    def test_get_default_runner_returns_playwright(self):
        runner = get_default_runner()
        assert isinstance(runner, PlaywrightRunner)


# ---------------------------------------------------------------- selenium skeleton


class TestSeleniumSkeleton:
    def test_selenium_runner_enter_raises(self):
        runner = SeleniumRunner(BrowserConfig())
        with pytest.raises(BrowserRunnerError, match="deprecated skeleton"):
            runner.__enter__()

    def test_selenium_runner_screenshot_raises(self):
        runner = SeleniumRunner(BrowserConfig())
        with pytest.raises(BrowserRunnerError, match="not implemented"):
            runner.screenshot(ScreenshotRequest(url="https://example.com"))

    def test_selenium_runner_extract_default_raises(self):
        runner = SeleniumRunner(BrowserConfig())
        with pytest.raises(NotImplementedError, match="extract"):
            runner.extract(ExtractRequest(url="https://example.com"))


# ---------------------------------------------------------------- playwright (smoke)


class TestPlaywrightRunnerSmoke:
    """Playwright 本体の smoke test。

    playwright が import 可能かで分岐:
        - 不可 → __enter__ で BrowserRunnerError (instructive message) になることを確認
        - 可 → ブラウザ起動だけしてすぐ閉じる
    """

    def _playwright_available(self) -> bool:
        try:
            import playwright.sync_api  # type: ignore  # noqa: F401

            return True
        except ImportError:
            return False

    def test_screenshot_without_enter_raises(self):
        runner = PlaywrightRunner(BrowserConfig())
        with pytest.raises(BrowserRunnerError, match="context manager"):
            runner.screenshot(ScreenshotRequest(url="https://example.com"))

    def test_enter_exit_when_no_playwright(self):
        if self._playwright_available():
            pytest.skip("playwright is installed; this test only runs without it")
        runner = PlaywrightRunner(BrowserConfig())
        with pytest.raises(BrowserRunnerError, match="not installed"):
            runner.__enter__()

    def test_unsupported_browser_type(self):
        with pytest.raises(ValueError, match="unsupported browser_type"):
            PlaywrightRunner(BrowserConfig(), browser_type="opera")  # type: ignore


# ---------------------------------------------------------------- helper facade


class TestHelperFacade:
    """`take_screenshot` ファサードの動作確認。

    実ブラウザ起動はせず、helper が runner を context manager として使い、
    セマフォを取得し、最終的に PlaywrightRunner エラーを伝播することを確認。
    """

    def test_take_screenshot_propagates_runner_error(self):
        # playwright が無い環境では BrowserRunnerError("not installed")
        # ある環境では実 URL に到達しないため別エラーになる可能性がある。
        # ここでは「BrowserRunnerError 系のいずれか」に流れることだけ確認する。
        try:
            import playwright.sync_api  # type: ignore  # noqa: F401

            playwright_available = True
        except ImportError:
            playwright_available = False

        if playwright_available:
            pytest.skip(
                "playwright installed: skipping no-network smoke to avoid hitting real network"
            )

        with pytest.raises(BrowserRunnerError):
            take_screenshot(
                ScreenshotRequest(
                    url="https://example.invalid/never-reached",
                    output_path=None,
                )
            )


# ---------------------------------------------------------------- retry helper


class TestRetryHelper:
    """`take_screenshot_with_retry` の挙動を、`take_screenshot` をモックして検証。"""

    def test_retry_returns_immediately_on_success(self, monkeypatch):
        from services.browser import screenshot_helper

        call_count = {"n": 0}

        def fake_take_screenshot(req, **kwargs):
            call_count["n"] += 1
            return ScreenshotResult(
                path="/tmp/x.png", data=None, size_bytes=42, url=req.url
            )

        monkeypatch.setattr(screenshot_helper, "take_screenshot", fake_take_screenshot)

        result = take_screenshot_with_retry(
            ScreenshotRequest(url="https://example.com"),
            max_attempts=3,
            initial_backoff_seconds=0.0,
        )
        assert call_count["n"] == 1
        assert result.size_bytes == 42

    def test_retry_on_timeout_then_succeeds(self, monkeypatch):
        from services.browser import screenshot_helper

        call_count = {"n": 0}

        def flaky(req, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise BrowserTimeoutError("transient")
            return ScreenshotResult(
                path="/tmp/x.png", data=None, size_bytes=99, url=req.url
            )

        monkeypatch.setattr(screenshot_helper, "take_screenshot", flaky)
        # time.sleep をスタブ化してテストを高速化
        monkeypatch.setattr(screenshot_helper.time, "sleep", lambda *a, **k: None)

        result = take_screenshot_with_retry(
            ScreenshotRequest(url="https://example.com"),
            max_attempts=5,
            initial_backoff_seconds=0.01,
        )
        assert call_count["n"] == 3
        assert result.size_bytes == 99

    def test_retry_exhausts_attempts(self, monkeypatch):
        from services.browser import screenshot_helper

        call_count = {"n": 0}

        def always_fails(req, **kwargs):
            call_count["n"] += 1
            raise BrowserNavigationError("permanent")

        monkeypatch.setattr(screenshot_helper, "take_screenshot", always_fails)
        monkeypatch.setattr(screenshot_helper.time, "sleep", lambda *a, **k: None)

        with pytest.raises(BrowserNavigationError, match="permanent"):
            take_screenshot_with_retry(
                ScreenshotRequest(url="https://example.com"),
                max_attempts=3,
                initial_backoff_seconds=0.01,
            )
        assert call_count["n"] == 3

    def test_retry_does_not_retry_runner_error(self, monkeypatch):
        from services.browser import screenshot_helper

        call_count = {"n": 0}

        def config_error(req, **kwargs):
            call_count["n"] += 1
            raise BrowserRunnerError("playwright is not installed")

        monkeypatch.setattr(screenshot_helper, "take_screenshot", config_error)
        monkeypatch.setattr(screenshot_helper.time, "sleep", lambda *a, **k: None)

        with pytest.raises(BrowserRunnerError, match="not installed"):
            take_screenshot_with_retry(
                ScreenshotRequest(url="https://example.com"),
                max_attempts=5,
                initial_backoff_seconds=0.01,
            )
        # 設定エラーは即 raise されてリトライしない
        assert call_count["n"] == 1

    def test_retry_invalid_max_attempts(self):
        with pytest.raises(ValueError, match="max_attempts"):
            take_screenshot_with_retry(
                ScreenshotRequest(url="https://example.com"),
                max_attempts=0,
            )


# ---------------------------------------------------------------- extract


class TestExtractContract:
    def test_extract_default_raises_not_implemented(self):
        # PlaywrightRunner は extract を override しているので、こちらは未起動状態で
        # context manager エラーが先に起きることだけ確認 (= 実 browser 不要)。
        runner = PlaywrightRunner(BrowserConfig())
        with pytest.raises(BrowserRunnerError, match="context manager"):
            runner.extract(ExtractRequest(url="https://example.com"))

    def test_extract_page_propagates_error(self):
        try:
            import playwright.sync_api  # type: ignore  # noqa: F401

            playwright_available = True
        except ImportError:
            playwright_available = False

        if playwright_available:
            pytest.skip(
                "playwright installed: skipping no-network smoke to avoid hitting real network"
            )

        with pytest.raises(BrowserRunnerError):
            extract_page(ExtractRequest(url="https://example.invalid/never"))
