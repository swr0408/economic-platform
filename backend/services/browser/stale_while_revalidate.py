"""Stale-While-Revalidate パターンの共通実装。

スクリーンショット取得など重い処理で、キャッシュ（古くても）を即座に返し、
バックグラウンドで更新を実行する。次回アクセス時に新しいデータが返る。

Usage::

    from backend.services.browser.stale_while_revalidate import background_revalidate

    def get_screenshot(self, force_refresh=False):
        cached = redis_client.get(self.CACHE_KEY)
        if cached and not force_refresh:
            # 古くても即座に返す。裏で更新を走らせる
            if self._is_stale(cached):
                background_revalidate(
                    f"swr:{self.CACHE_KEY}",
                    self._capture_and_cache,
                )
            return cached_response

        # force_refresh の場合は同期で取得
        return self._capture_and_cache()
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 実行中のバックグラウンドタスクを追跡（重複起動を防止）
_running_tasks: set[str] = set()
_lock = threading.Lock()


def background_revalidate(
    task_key: str,
    fn: Callable[[], None],
    *,
    timeout_seconds: float = 120,
) -> bool:
    """バックグラウンドスレッドで ``fn`` を実行する。

    同じ ``task_key`` のタスクが既に実行中の場合はスキップする
    （同じスクショの多重取得を防止）。

    Args:
        task_key: タスク識別キー (例: ``"swr:usa:fedwatch:screenshot"``)
        fn: バックグラウンドで実行する関数（引数なし）
        timeout_seconds: タイムアウト（デーモンスレッドなので強制終了はしない）

    Returns:
        True: 新しいバックグラウンドタスクを起動した
        False: 既に同じタスクが実行中のためスキップした
    """
    with _lock:
        if task_key in _running_tasks:
            logger.debug(f"[SWR] task already running: {task_key}")
            return False
        _running_tasks.add(task_key)

    def _worker() -> None:
        try:
            logger.info(f"[SWR] background revalidation started: {task_key}")
            fn()
            logger.info(f"[SWR] background revalidation completed: {task_key}")
        except Exception:
            logger.exception(f"[SWR] background revalidation failed: {task_key}")
        finally:
            with _lock:
                _running_tasks.discard(task_key)

    thread = threading.Thread(target=_worker, name=f"swr-{task_key}", daemon=True)
    thread.start()
    return True


def is_revalidating(task_key: str) -> bool:
    """指定タスクがバックグラウンドで実行中かどうかを返す。"""
    with _lock:
        return task_key in _running_tasks
