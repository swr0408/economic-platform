"""ブラウザランナー共通例外クラス。

既存の screenshot サービスが Playwright / Selenium 各々の例外型に直接
依存しているのを、ここで定義した共通例外に集約していく。
"""
from __future__ import annotations


class BrowserRunnerError(Exception):
    """ブラウザランナー全般の基底例外。"""


class BrowserTimeoutError(BrowserRunnerError):
    """ナビゲーション/セレクタ待機等のタイムアウト。"""


class BrowserNavigationError(BrowserRunnerError):
    """URL 取得自体に失敗 (DNS, TLS, HTTP エラー等)。"""
