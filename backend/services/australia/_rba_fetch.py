"""
RBA 共通ダウンロードヘルパー

背景 (2026-06 調査):
- RBA の WAF (Akamai) が「ブラウザ風 User-Agent なのに TLS フィンガープリントが
  ブラウザでない」リクエストを 403 で拒否するようになった
  （Chrome UA + python-requests/curl → 403、ツール系デフォルト UA → 200）。
- そのため Chrome UA を偽装していた既存サービスが一斉に 403 でサイレント stale 化した。

方針:
1. requests をデフォルト UA（python-requests/x.y）のまま使用 ← 現在これが通る
2. 失敗時は curl サブプロセス（curl デフォルト UA）にフォールバック
3. xlsx マジックバイト (PK\\x03\\x04) で検証し、HTML 偽装レスポンスを明示的に拒否
"""
import logging
import os
import subprocess
import tempfile
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# xlsx (zip) マジックバイト
XLSX_MAGIC = b"PK\x03\x04"


def _is_valid_xlsx(content: Optional[bytes]) -> bool:
    """xlsx として妥当か（HTML エラーページ偽装を弾く）"""
    return bool(content) and content.startswith(XLSX_MAGIC)


def fetch_rba_xlsx(url: str, timeout: int = 90) -> Optional[bytes]:
    """RBA から xlsx をダウンロード（WAF 403 対策込み）

    重要: ブラウザ UA を偽装しないこと。RBA の WAF は
    「ブラウザ UA × 非ブラウザ TLS」の組み合わせを 403 で弾く。

    Args:
        url: RBA xlsx の URL
        timeout: タイムアウト秒

    Returns:
        xlsx バイト列、失敗時 None（失敗は必ずログに残す）
    """
    # 1) requests（デフォルト UA のまま = 正直なツール UA）
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200 and _is_valid_xlsx(resp.content):
            logger.info(f"[RBA fetch] requests OK: {url} ({len(resp.content)} bytes)")
            return resp.content
        logger.warning(
            f"[RBA fetch] requests rejected: HTTP {resp.status_code}, "
            f"head={resp.content[:16]!r}: {url}"
        )
    except Exception as e:
        logger.warning(f"[RBA fetch] requests error: {e}: {url}")

    # 2) curl サブプロセス フォールバック（curl デフォルト UA）
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        proc = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(timeout), "-o", tmp_path, url],
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        if proc.returncode == 0:
            with open(tmp_path, "rb") as f:
                content = f.read()
            if _is_valid_xlsx(content):
                logger.info(f"[RBA fetch] curl fallback OK: {url} ({len(content)} bytes)")
                return content
            logger.error(
                f"[RBA fetch] curl returned non-xlsx content "
                f"(head={content[:16]!r}, {len(content)} bytes): {url}"
            )
        else:
            logger.error(
                f"[RBA fetch] curl failed (exit {proc.returncode}): {proc.stderr[:200]}"
            )
    except Exception as e:
        logger.error(f"[RBA fetch] curl fallback error: {e}: {url}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    logger.error(f"[RBA fetch] ERROR: all download methods failed for {url}")
    return None
