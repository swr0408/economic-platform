"""
RBNZ 共通ダウンロードヘルパー

背景 (2026-06 調査):
- RBNZ (rbnz.govt.nz) は Cloudflare 保護下にあり、python-requests / cloudscraper は
  UA に関係なく 403 (Cloudflare challenge HTML) で弾かれる。
- curl / wget の CLI は通る ← 現状唯一の確実な手段（ただし断続的に 403 を返すので要リトライ）。
- 環境によりどちらが入っているか異なる: 本番 Dockerfile.simple は **wget のみ**、
  別構成 Dockerfile は **curl のみ**。→ shutil.which で在る方を自動選択し両対応する。
  （curl 決め打ちだと本番コンテナで FileNotFoundError → cloudscraper → CF 403 → stale 化していた）
- 旧実装は「ダウンロードサイズ < 5000 bytes なら失敗」のサイレント判定だったため、
  CF 403 HTML を握り潰して stale 化していた → xlsx マジックバイトで明示検証する。

方針:
1. curl / wget の在る方をリトライ付きで実行（プライマリ）
2. cloudscraper フォールバック（CLI が全滅した場合の保険）
3. xlsx マジックバイト (PK\\x03\\x04) で検証し、CF challenge HTML を明示的に検出してログ
"""
import logging
import os
import shutil
import subprocess
import tempfile
import time
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# xlsx (zip) マジックバイト
XLSX_MAGIC = b"PK\x03\x04"

CURL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Cloudflare 断続 403 対策のリトライ回数（curl/wget 共通）
MAX_CLI_ATTEMPTS = 5
CLI_BACKOFF_SEC = 3


def _looks_like_xlsx(content: Optional[bytes]) -> bool:
    """xlsx (zip) マジックバイトを持つか"""
    return bool(content) and content.startswith(XLSX_MAGIC)


def _describe_non_xlsx(content: Optional[bytes], method: str) -> str:
    """xlsx でない応答の理由を説明する文字列（ログ用）"""
    if not content:
        return f"{method}: empty response"
    head = content[:200].decode("utf-8", errors="replace")
    if "<!DO" in head or "<html" in head.lower() or "cloudflare" in head.lower():
        return f"{method}: BLOCKED — Cloudflare/HTML page ({len(content)} bytes)"
    return f"{method}: non-xlsx content (head={content[:16]!r})"


def _available_cli_downloaders(url: str, dest_path: str, timeout: int) -> List[Tuple[str, List[str]]]:
    """利用可能な CLI ダウンローダ (curl / wget) のコマンドを返す。

    本番 Dockerfile.simple は wget のみ、別構成は curl のみのため shutil.which で両対応。
    """
    downloaders: List[Tuple[str, List[str]]] = []
    if shutil.which("curl"):
        downloaders.append((
            "curl",
            ["curl", "-L", "-sS", "-H", f"User-Agent: {CURL_UA}",
             "--max-time", str(timeout), "-o", dest_path, url],
        ))
    if shutil.which("wget"):
        downloaders.append((
            "wget",
            ["wget", "-q", "-O", dest_path,
             f"--header=User-Agent: {CURL_UA}", f"--timeout={timeout}", url],
        ))
    return downloaders


def fetch_rbnz_xlsx(url: str, timeout: int = 120) -> Optional[bytes]:
    """RBNZ から xlsx をダウンロード（Cloudflare 403 対策込み）

    Args:
        url: RBNZ xlsx の URL
        timeout: タイムアウト秒

    Returns:
        xlsx バイト列、失敗時 None（失敗は必ず ERROR ログに残す）
    """
    # 1) curl / wget の在る方をリトライ付きで実行
    failures: List[str] = []
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        downloaders = _available_cli_downloaders(url, tmp_path, timeout)
        if not downloaders:
            logger.warning("[RBNZ fetch] neither curl nor wget available; trying cloudscraper")

        for attempt in range(1, MAX_CLI_ATTEMPTS + 1):
            for name, cmd in downloaders:
                try:
                    proc = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=timeout + 30
                    )
                except Exception as e:
                    failures.append(f"{name} #{attempt}: {e}")
                    continue

                if proc.returncode != 0:
                    failures.append(f"{name} #{attempt}: exit {proc.returncode} {proc.stderr[:120]}")
                    continue

                try:
                    with open(tmp_path, "rb") as f:
                        content = f.read()
                except Exception as e:
                    failures.append(f"{name} #{attempt}: read error {e}")
                    continue

                if _looks_like_xlsx(content):
                    logger.info(f"[RBNZ fetch] {name} OK (attempt {attempt}): {url} ({len(content)} bytes)")
                    return content
                failures.append(_describe_non_xlsx(content, f"{name} #{attempt}"))

            # 次の試行まで待つ（Cloudflare 断続 403 対策）
            if downloaders and attempt < MAX_CLI_ATTEMPTS:
                time.sleep(CLI_BACKOFF_SEC)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    # 2) cloudscraper フォールバック（CLI が全滅した場合の保険）
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=timeout)
        if resp.status_code == 200 and _looks_like_xlsx(resp.content):
            logger.info(f"[RBNZ fetch] cloudscraper OK: {url} ({len(resp.content)} bytes)")
            return resp.content
        failures.append(f"cloudscraper: HTTP {resp.status_code}")
    except Exception as e:
        failures.append(f"cloudscraper: {e}")

    logger.error(
        f"[RBNZ fetch] ERROR: all download methods failed for {url} — "
        f"last failures: {failures[-4:]}"
    )
    return None
