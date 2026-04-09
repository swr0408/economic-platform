"""ブラウザ実行の同時並列数を制御するセマフォ。

OCI Always Free (1 OCPU / 6GB) で Chromium を複数起動するとメモリ枯渇の
リスクがあるため、プロセス全体で 2 並列までに制限する。

使い方:

    from backend.services.browser.concurrency import browser_semaphore

    with browser_semaphore:
        # ここで Playwright / Selenium を起動
        ...

注意:
    - これはプロセス内 (= 1 backend コンテナ内) のセマフォで、複数レプリカを
      跨いだ制御はしない。将来的にブラウザワーカーを別コンテナに分離した
      場合は、ワーカー側でキューを持つ前提。
    - APScheduler のジョブと FastAPI リクエストハンドラから同時に呼ばれて
      も安全 (threading.BoundedSemaphore はスレッドセーフ)。
"""
from __future__ import annotations

import os
import threading

# 環境変数で上書き可能 (テスト時に 1 にしたいケース等)
_DEFAULT_CONCURRENCY = 2
try:
    _CONCURRENCY = int(os.environ.get("BROWSER_RUNNER_CONCURRENCY", _DEFAULT_CONCURRENCY))
    if _CONCURRENCY < 1:
        _CONCURRENCY = _DEFAULT_CONCURRENCY
except (TypeError, ValueError):
    _CONCURRENCY = _DEFAULT_CONCURRENCY


browser_semaphore: threading.BoundedSemaphore = threading.BoundedSemaphore(value=_CONCURRENCY)
"""プロセス全体で共有するブラウザ実行セマフォ。"""


def get_concurrency_limit() -> int:
    """現在の同時実行上限を返す (テスト/監視用)。"""
    return _CONCURRENCY
