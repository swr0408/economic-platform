"""
RBNZ 共通ダウンロードヘルパー

背景 (2026-06 調査):
- RBNZ (rbnz.govt.nz) は Cloudflare 保護下にあり、python-requests / cloudscraper は
  UA に関係なく 403 (Cloudflare challenge HTML) で弾かれる。
- curl (Windows では Schannel TLS) は 200 で通る ← 現状唯一の確実な手段。
- 旧実装は「ダウンロードサイズ < 5000 bytes なら失敗」のサイレント判定だったため、
  CF 403 HTML を握り潰して stale 化していた。

方針:
1. curl サブプロセス（プライマリ）
2. cloudscraper フォールバック（curl が将来ブロックされた場合の保険）
3. xlsx マジックバイト (PK\\x03\\x04) で検証し、CF challenge HTML を明示的に検出してログ
"""
import logging
import os
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# xlsx (zip) マジックバイト
XLSX_MAGIC = b"PK\x03\x04"

CURL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _validate_xlsx(content: Optional[bytes], url: str, method: str) -> bool:
    """xlsx として妥当かを検証し、CF ブロック等は明確にログを残す"""
    if not content:
        logger.error(f"[RBNZ fetch] {method}: empty response: {url}")
        return False
    if content.startswith(XLSX_MAGIC):
        return True
    head = content[:200].decode("utf-8", errors="replace")
    if "<!DO" in head or "<html" in head.lower() or "cloudflare" in head.lower():
        # 旧実装ではここがサイレントに握り潰されて stale 化していた
        logger.error(
            f"[RBNZ fetch] {method}: BLOCKED — Cloudflare/HTML page returned "
            f"instead of xlsx ({len(content)} bytes): {url}"
        )
    else:
        logger.error(
            f"[RBNZ fetch] {method}: non-xlsx content (head={content[:16]!r}): {url}"
        )
    return False


def fetch_rbnz_xlsx(url: str, timeout: int = 120) -> Optional[bytes]:
    """RBNZ から xlsx をダウンロード（Cloudflare 403 対策込み）

    Args:
        url: RBNZ xlsx の URL
        timeout: タイムアウト秒

    Returns:
        xlsx バイト列、失敗時 None（失敗は必ず ERROR ログに残す）
    """
    # 1) curl サブプロセス（Schannel TLS フィンガープリントが CF を通過する）
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        proc = subprocess.run(
            [
                "curl", "-L", "-sS",
                "-H", f"User-Agent: {CURL_UA}",
                "--max-time", str(timeout),
                "-o", tmp_path,
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        if proc.returncode == 0:
            with open(tmp_path, "rb") as f:
                content = f.read()
            if _validate_xlsx(content, url, "curl"):
                logger.info(f"[RBNZ fetch] curl OK: {url} ({len(content)} bytes)")
                return content
        else:
            logger.error(
                f"[RBNZ fetch] curl failed (exit {proc.returncode}): "
                f"{proc.stderr[:200]}: {url}"
            )
    except Exception as e:
        logger.error(f"[RBNZ fetch] curl error: {e}: {url}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    # 2) cloudscraper フォールバック
    #    （2026-06 時点では CF に弾かれるが、curl 側が死んだ時の保険として残す）
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=timeout)
        if resp.status_code == 200 and _validate_xlsx(resp.content, url, "cloudscraper"):
            logger.info(f"[RBNZ fetch] cloudscraper OK: {url} ({len(resp.content)} bytes)")
            return resp.content
        logger.error(
            f"[RBNZ fetch] cloudscraper rejected: HTTP {resp.status_code}: {url}"
        )
    except Exception as e:
        logger.error(f"[RBNZ fetch] cloudscraper error: {e}: {url}")

    logger.error(f"[RBNZ fetch] ERROR: all download methods failed for {url}")
    return None
