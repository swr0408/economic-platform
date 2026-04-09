"""Selenium ベースの BrowserRunner 実装 (互換用スケルトン / 廃止予定)。

このクラスは **積極的に新規利用すべきではない**。

存在理由:
    - 既存の Selenium ベースの 13 サービスを 1 つずつ Playwright に移行する
      過渡期に、共通インターフェースの「もう一方の実装」として contract test
      を成立させるための skeleton。
    - 将来的に何らかの理由で Selenium が必要になった場合 (例: 特定の
      WebDriver 拡張に依存する社内ツール) に、すぐ実装に取りかかれるよう
      テンプレートを残しておく。

実装方針:
    - `__enter__` / `__exit__` は **未実装** (NotImplementedError) のまま。
    - `screenshot()` も同様。
    - import 自体は失敗させない (selenium パッケージ非依存)。

OCI 移行後 (browser-worker コンテナ) では、このファイルは削除予定。
"""
from __future__ import annotations

from typing import Optional

from .exceptions import BrowserRunnerError
from .runner import BrowserConfig, BrowserRunner, ScreenshotRequest, ScreenshotResult


class SeleniumRunner(BrowserRunner):
    """Selenium WebDriver ベースの実装 (未実装の skeleton)。

    新規実装では PlaywrightRunner を使うこと。
    """

    def __init__(
        self,
        config: Optional[BrowserConfig] = None,
        driver_type: str = "chrome",
    ) -> None:
        super().__init__(config)
        self.driver_type: str = driver_type
        self._driver = None

    def __enter__(self) -> "SeleniumRunner":
        raise BrowserRunnerError(
            "SeleniumRunner is a deprecated skeleton. Use PlaywrightRunner. "
            "If you really need Selenium, implement this method against "
            "selenium.webdriver and ensure ARM64 chromedriver availability."
        )

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def screenshot(self, request: ScreenshotRequest) -> ScreenshotResult:
        raise BrowserRunnerError(
            "SeleniumRunner.screenshot is not implemented. Use PlaywrightRunner."
        )
