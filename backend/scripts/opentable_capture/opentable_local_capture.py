#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenTable レストラン予約件数 ローカル自動キャプチャ & アップロード

なぜローカルで動かすか:
  OpenTable の State of the Industry ページは Akamai Bot Manager 配下で、
  bundled Chromium / データセンターIP / OCI ARM64(=Google Chrome非搭載) からは
  遮断される。**実物の Google Chrome (channel='chrome') + 住宅IP** でのみ突破可能。
  そのため本スクリプトは「実Chromeが動くローカルPC」で週次/月次スクショを撮り、
  バックエンドの `POST /api/usa/opentable/upload` に投稿する（＝サーバ常駐の完全
  自動化の代替となる半自動運用）。Windows タスクスケジューラでの日次実行を想定。

必要環境:
  - Python (playwright 導入済み)  … `pip install playwright`
  - Google Chrome 本体            … channel='chrome' で使用（インストール済みが前提）
  - バックエンドが稼働（既定 http://localhost:8000）

設定（環境変数）:
  ECONALPHA_API_BASE            バックエンドURL（既定 http://localhost:8000）
  ECONALPHA_USERNAME            master ユーザー名（アップロードに master 権限が必要）
  ECONALPHA_PASSWORD            master パスワード
  OPENTABLE_WEEKLY_GEOGRAPHY    週次チャートの地域（既定 "United States" / "Global" 等）
  OPENTABLE_CHROME_CHANNEL      Playwright チャンネル（既定 "chrome"）
  OPENTABLE_HEADLESS            "0" でブラウザ表示（デバッグ用、既定は非表示=headless）

使い方:
  python opentable_local_capture.py            # 撮影してアップロード
  python opentable_local_capture.py --dry-run  # 撮影のみ（png をこのフォルダに保存、投稿しない）
  python opentable_local_capture.py --headful  # ブラウザを表示して撮影

終了コード: 0=成功 / 非0=失敗（タスクスケジューラで失敗検知できる）
"""
import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

OPENTABLE_URL = "https://www.opentable.com/state-of-industry"

# キャプチャ対象セクション（feasibility 検証で確定したセレクタ）
WEEKLY_SECTION = ".r9-soti-graph-section"   # 週次ラインチャート（svg）
MONTHLY_SECTION = ".r9-soti-table-section"  # 月次テーブル（国×月）

API_BASE = os.environ.get("ECONALPHA_API_BASE", "http://localhost:8000").rstrip("/")
USERNAME = os.environ.get("ECONALPHA_USERNAME", "")
PASSWORD = os.environ.get("ECONALPHA_PASSWORD", "")
WEEKLY_GEOGRAPHY = os.environ.get("OPENTABLE_WEEKLY_GEOGRAPHY", "United States")
CHROME_CHANNEL = os.environ.get("OPENTABLE_CHROME_CHANNEL", "chrome")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

logger = logging.getLogger("opentable_capture")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(SCRIPT_DIR / "opentable_capture.log", encoding="utf-8"),
        ],
    )


# --------------------------------------------------------------------------- HTTP

def _login() -> str:
    """master でログインして JWT アクセストークンを取得する。"""
    if not USERNAME or not PASSWORD:
        raise RuntimeError(
            "ECONALPHA_USERNAME / ECONALPHA_PASSWORD が未設定です "
            "(run_opentable_capture.bat に master 認証情報を設定してください)"
        )
    url = f"{API_BASE}/api/auth/login"
    body = json.dumps({"username": USERNAME, "password": PASSWORD}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"login failed: HTTP {e.code} {detail}") from e
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"login response に access_token がありません: {data}")
    logger.info("login OK (user=%s)", USERNAME)
    return token


def _upload(token: str, captures: dict) -> dict:
    """撮影した png を multipart で /api/usa/opentable/upload に投稿する。

    captures: {"week": bytes, "month": bytes}（いずれか一方でも可）
    """
    url = f"{API_BASE}/api/usa/opentable/upload"
    boundary = uuid.uuid4().hex
    parts = []
    for field, data in captures.items():
        if not data:
            continue
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{field}"; '
            f'filename="{field}.png"\r\n'.encode()
        )
        parts.append(b"Content-Type: image/png\r\n\r\n")
        parts.append(data)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    payload = b"".join(parts)

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"upload failed: HTTP {e.code} {detail}") from e


# --------------------------------------------------------------------------- capture

def _accept_cookie(page) -> None:
    for sel in (
        "#onetrust-accept-btn-handler",
        'button:has-text("Accept")',
        'button:has-text("Agree")',
    ):
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                el.click()
                page.wait_for_timeout(800)
                logger.info("cookie banner closed via %s", sel)
                return
        except Exception:
            continue


def _select_in_section(page, section_sel: str, want_label: str) -> bool:
    """section 内の <select> のうち want_label を選択肢に持つものを選択する。

    週次チャートの地域(United States 等) / 月次テーブルの粒度(Monthly) 切替に使う。
    見つからなければ False（既定表示のまま撮影を続ける）。
    """
    try:
        selects = page.query_selector_all(f"{section_sel} select")
    except Exception:
        selects = []
    for sel in selects:
        try:
            labels = sel.evaluate("el => Array.from(el.options).map(o => o.text.trim())")
            if want_label in labels:
                sel.select_option(label=want_label)
                page.wait_for_timeout(2500)  # チャート/テーブル再描画待ち
                logger.info("selected '%s' in %s", want_label, section_sel)
                return True
        except Exception:
            continue
    logger.warning("could not select '%s' in %s (using default view)", want_label, section_sel)
    return False


def _shoot(page, section_sel: str) -> bytes | None:
    try:
        el = page.query_selector(section_sel)
        if el is None:
            logger.error("section not found: %s", section_sel)
            return None
        el.scroll_into_view_if_needed()
        page.wait_for_timeout(600)
        return el.screenshot(type="png")
    except Exception as e:
        logger.error("screenshot failed for %s: %s", section_sel, e)
        return None


def capture(headless: bool = True) -> dict:
    """週次チャートと月次テーブルを撮影し {"week": bytes, "month": bytes} を返す。"""
    from playwright.sync_api import sync_playwright

    result: dict = {}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                channel=CHROME_CHANNEL,
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        except Exception as e:
            raise RuntimeError(
                f"Google Chrome の起動に失敗しました (channel='{CHROME_CHANNEL}'): {e}\n"
                "Google Chrome 本体がインストールされているか確認してください。"
            ) from e

        ctx = browser.new_context(
            viewport={"width": 1400, "height": 1600},
            user_agent=USER_AGENT,
        )
        page = ctx.new_page()
        logger.info("navigating to %s", OPENTABLE_URL)
        page.goto(OPENTABLE_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        _accept_cookie(page)

        # チャート描画のためネットワーク沈静化を待つ（届かなくても続行）
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            logger.info("networkidle not reached; continuing")
        page.wait_for_timeout(4000)
        logger.info("page title: %s", page.title())

        # 週次: 地域を選択（既定 United States）／ 月次: 粒度を Monthly に
        _select_in_section(page, WEEKLY_SECTION, WEEKLY_GEOGRAPHY)
        _select_in_section(page, MONTHLY_SECTION, "Monthly")
        page.wait_for_timeout(1500)

        week = _shoot(page, WEEKLY_SECTION)
        month = _shoot(page, MONTHLY_SECTION)
        if week:
            result["week"] = week
            logger.info("captured weekly chart (%d bytes)", len(week))
        if month:
            result["month"] = month
            logger.info("captured monthly table (%d bytes)", len(month))

        browser.close()
    return result


# --------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description="OpenTable local capture & upload")
    parser.add_argument("--dry-run", action="store_true",
                        help="撮影のみ（png をこのフォルダに保存し、アップロードしない）")
    parser.add_argument("--headful", action="store_true",
                        help="ブラウザを表示して撮影（デバッグ用）")
    args = parser.parse_args()

    headless = not args.headful and os.environ.get("OPENTABLE_HEADLESS", "1") != "0"

    logger.info("=== OpenTable capture start (api=%s, geo=%s, dry_run=%s) ===",
                API_BASE, WEEKLY_GEOGRAPHY, args.dry_run)

    captures = capture(headless=headless)
    if not captures:
        logger.error("no captures produced; aborting")
        return 2

    if args.dry_run:
        for field, data in captures.items():
            out = SCRIPT_DIR / f"opentable_{field}.png"
            out.write_bytes(data)
            logger.info("dry-run saved %s", out)
        logger.info("=== dry-run done (uploaded nothing) ===")
        return 0

    token = _login()
    resp = _upload(token, captures)
    saved = resp.get("saved", [])
    logger.info("upload OK: %s", [s.get("filename") for s in saved])
    logger.info("=== OpenTable capture done ===")
    return 0


if __name__ == "__main__":
    _setup_logging()
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception("FATAL: %s", e)
        sys.exit(1)
