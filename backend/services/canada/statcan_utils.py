"""Statistics Canada CSV ZIP の共有ダウンロード/パースキャッシュ。

複数サービスが同じ StatCan テーブル (例: 36-10-0434-01 = 月次GDP) を
それぞれ別個にダウンロードしていた問題を解消する。

- 同一 URL に対し、最大 600秒 (10分) DataFrame をプロセス内メモリにキャッシュ
- URL 単位のロックで thundering herd を防止 (同時並行ダウンロード抑止)
- ChunkedEncodingError / Timeout に対する指数バックオフ再試行

注意:
- 返却される DataFrame は読み取り専用扱い。改変したい呼出側は ``.copy()`` する
- キャッシュ対象は CSV パース後の DataFrame のため、リクエスト数だけでなく
  CSV パースコスト (~30MB → 数十万行) も削減できる
"""
from __future__ import annotations

import io
import logging
import threading
import time
import zipfile
from typing import Dict, Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600
_REQUEST_TIMEOUT = 90
_DOWNLOAD_RETRIES = 2

_cache_lock = threading.Lock()
_cache: Dict[str, Tuple[float, pd.DataFrame]] = {}

_download_locks_lock = threading.Lock()
_download_locks: Dict[str, threading.Lock] = {}


def _get_download_lock(url: str) -> threading.Lock:
    with _download_locks_lock:
        lock = _download_locks.get(url)
        if lock is None:
            lock = threading.Lock()
            _download_locks[url] = lock
        return lock


def _read_cached(url: str) -> pd.DataFrame | None:
    with _cache_lock:
        entry = _cache.get(url)
        if entry is None:
            return None
        ts, df = entry
        if time.time() - ts >= _CACHE_TTL_SECONDS:
            return None
        return df


def fetch_statcan_csv(url: str) -> pd.DataFrame:
    """StatCan ZIP をダウンロードし、内包 CSV を DataFrame として返す。

    同一 URL は ``_CACHE_TTL_SECONDS`` 内なら再ダウンロードしない。
    並行呼出は URL 単位ロックで一本化される。

    Raises:
        requests.exceptions.RequestException: リトライ上限を超えても失敗した場合
    """
    cached = _read_cached(url)
    if cached is not None:
        return cached

    lock = _get_download_lock(url)
    with lock:
        # ダブルチェック: ロック取得中に別スレッドが取得済みの可能性
        cached = _read_cached(url)
        if cached is not None:
            return cached

        last_err: Exception | None = None
        for attempt in range(_DOWNLOAD_RETRIES + 1):
            try:
                logger.info(f"[StatCan] Fetching {url} (attempt {attempt + 1})")
                resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
                resp.raise_for_status()
                zf = zipfile.ZipFile(io.BytesIO(resp.content))
                csv_name = next(
                    n for n in zf.namelist()
                    if n.endswith(".csv") and not n.startswith("_")
                )
                with zf.open(csv_name) as f:
                    df = pd.read_csv(f, low_memory=False)

                with _cache_lock:
                    _cache[url] = (time.time(), df)
                logger.info(f"[StatCan] Cached {url} ({len(df)} rows)")
                return df

            except (
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as e:
                last_err = e
                if attempt < _DOWNLOAD_RETRIES:
                    backoff = 2 ** attempt
                    logger.warning(
                        f"[StatCan] {url} transient error ({e}); retry in {backoff}s"
                    )
                    time.sleep(backoff)
                    continue
                logger.error(f"[StatCan] {url} failed after retries: {e}")
                raise

        assert last_err is not None
        raise last_err


def invalidate_cache(url: str | None = None) -> None:
    """キャッシュを明示的に無効化 (主にテスト用)。"""
    with _cache_lock:
        if url is None:
            _cache.clear()
        else:
            _cache.pop(url, None)
