"""requests ライブラリのデフォルトタイムアウト設定。

タイムアウト未指定の requests.get/post 等が無限にハングするのを防ぐ。
アプリ起動時に一度だけ import すればよい。

仕組み:
  requests.adapters.HTTPAdapter.send() をラップし、timeout が None の場合に
  デフォルト値 (connect=10s, read=30s) を挿入する。
  既に timeout が指定されている呼び出しには干渉しない。
"""
import logging

import requests.adapters

logger = logging.getLogger(__name__)

# (connect_timeout, read_timeout)
DEFAULT_TIMEOUT = (10, 30)

_original_send = requests.adapters.HTTPAdapter.send


def _send_with_timeout(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    return _original_send(self, request, stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies)


requests.adapters.HTTPAdapter.send = _send_with_timeout  # type: ignore[assignment]

logger.info(f"[http_defaults] requests default timeout set to {DEFAULT_TIMEOUT}")
