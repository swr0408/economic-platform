"""
OpenTable Seated Diners サービス
OpenTableからレストラン予約件数前年比チャートのスクリーンショットを取得

データソース: https://www.opentable.com/state-of-industry

更新スケジュール:
- 毎日更新（米国時間で日次更新、JST 10:00頃を想定）
- 日次データ

キャッシュ方式: last_updated判定（24時間有効、データ更新時に自動リフレッシュ）

[移行ノート]
このサービスは backend.services.browser.PlaywrightRunner 経由に統一済み
(ARM64 / OCI 対応)。以前の Playwright 直接利用はすべて削除。
旧実装の以下ロジックを `pre_screenshot_js` でブラウザ内 JS に集約:
    1. 地域セレクタ <select aria-label="Select location for data"> を
       value="840" (United States) に切り替え + change イベント発火
    2. ページ中央までスクロール (Seated Diners セクション表示用)
    3. 候補セレクタ列を順に試して 300x200 以上の最初のチャート要素を
       data-opentable-target="1" 属性で印を付ける
"""
import base64
import logging
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.browser import (
    BrowserConfig,
    BrowserRunnerError,
    ScreenshotRequest,
    take_screenshot_with_retry,
)

logger = logging.getLogger(__name__)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
ET = ZoneInfo("America/New_York")

# スクリーンショット保存ディレクトリ
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "/app/screenshots"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# OpenTable URL
OPENTABLE_URL = "https://www.opentable.com/state-of-industry"


class OpenTableService:
    """
    OpenTable Seated Diners サービス
    レストラン予約件数前年比チャートのスクリーンショットを取得
    """

    CACHE_KEY = "usa:opentable:screenshot"
    # キャッシュTTL: 24時間（日次データ）
    CACHE_TTL = 24 * 60 * 60  # 86400秒

    # 旧 Playwright 実装の以下ロジックをブラウザ内 JS で再現する:
    #   1. select[aria-label="Select location for data"] を value="840"
    #      (United States) に変更し change イベントを発火
    #   2. ページ高さ * 0.5 まで scrollTo
    #   3. 候補セレクタを順に試して 300x200 以上の要素を
    #      data-opentable-target="1" でマーキング
    # スクショ対象は ScreenshotRequest.clip_selector で参照する。
    _PRE_SCREENSHOT_JS = r"""
    (() => {
      // Step 1: 地域セレクタを United States に切り替え
      try {
        let geoSelect = document.querySelector(
          'select[aria-label="Select location for data"]'
        );
        if (!geoSelect) {
          // フォールバック: United States option を持つ select を探す
          const allSelects = Array.from(document.querySelectorAll('select'));
          for (const sel of allSelects) {
            const opts = Array.from(sel.options || []).map(o => o.text);
            if (opts.indexOf('United States') !== -1) {
              geoSelect = sel;
              break;
            }
          }
        }
        if (geoSelect) {
          // value="840" を試行、無ければ label "United States" を選択
          const opts = Array.from(geoSelect.options || []);
          let target = opts.find(o => o.value === '840');
          if (!target) target = opts.find(o => (o.text || '').trim() === 'United States');
          if (target) {
            geoSelect.value = target.value;
            geoSelect.dispatchEvent(new Event('change', {bubbles: true}));
            geoSelect.dispatchEvent(new Event('input', {bubbles: true}));
          }
        }
      } catch (e) { /* noop */ }

      // Step 2: ページ中央までスクロール
      try {
        window.scrollTo(0, document.body.scrollHeight * 0.5);
      } catch (e) { /* noop */ }

      // Step 3: チャート候補要素をマーキング
      const selectors = [
        '#seated-diners-chart',
        '[class*="seated-diners"]',
        '.r9-soti-controls',
        '[class*="chart"]',
        'canvas',
        '.highcharts-container',
        '[id*="highcharts"]',
      ];
      document.querySelectorAll('[data-opentable-target]')
        .forEach(el => el.removeAttribute('data-opentable-target'));
      for (const sel of selectors) {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
          const r = el.getBoundingClientRect();
          if (r.width > 300 && r.height > 200) {
            el.setAttribute('data-opentable-target', '1');
            el.scrollIntoView({block: 'center'});
            return true;
          }
        }
      }
      return false;
    })();
    """

    def __init__(self):
        self.screenshot_path = SCREENSHOT_DIR / "opentable_seated_diners.png"

    def get_opentable_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        OpenTableチャートデータを取得

        Returns:
            {
                "image_url": str,  # 画像へのパス
                "latest": {"date": str, "description": str},
                "last_updated": str,
                "cached": bool,
                "source": str
            }
        """
        # 1. キャッシュをチェック
        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "image_url": "/static/screenshots/opentable_seated_diners.png",
                        "latest": self._get_latest_info(),
                        "last_updated": last_updated_str,
                        "cached": True,
                        "source": "redis"
                    }

        # 2. ファイルキャッシュをチェック
        if not force_refresh and self.screenshot_path.exists():
            file_mtime = datetime.fromtimestamp(
                self.screenshot_path.stat().st_mtime,
                tz=JST
            )
            if not self._should_refresh(file_mtime.isoformat()):
                cache_data = {
                    "last_updated": file_mtime.isoformat()
                }
                redis_client.set(self.CACHE_KEY, cache_data, expire=self.CACHE_TTL)
                return {
                    "image_url": "/static/screenshots/opentable_seated_diners.png",
                    "latest": self._get_latest_info(),
                    "last_updated": file_mtime.isoformat(),
                    "cached": True,
                    "source": "file"
                }

        # 3. 新しいスクリーンショットを取得
        success = self._capture_screenshot()

        if success:
            cache_data = {
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_data, expire=self.CACHE_TTL)

            return {
                "image_url": "/static/screenshots/opentable_seated_diners.png",
                "latest": self._get_latest_info(),
                "last_updated": cache_data["last_updated"],
                "cached": False,
                "source": "playwright"
            }

        # 4. 失敗時は既存のスクリーンショットを返す
        if self.screenshot_path.exists():
            return {
                "image_url": "/static/screenshots/opentable_seated_diners.png",
                "latest": self._get_latest_info(),
                "last_updated": None,
                "cached": True,
                "source": "file_stale",
                "error": "Failed to capture new screenshot"
            }

        return {
            "image_url": None,
            "latest": None,
            "last_updated": None,
            "cached": False,
            "source": "none",
            "error": "No screenshot available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - 日次データなので、最終更新から24時間経過していれば更新
        - または、ETで日付が変わり、ET 10:00以降であれば更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 24時間経過していれば更新
            if (now - last_updated).total_seconds() >= self.CACHE_TTL:
                return True

            # ET日付が変わっていれば更新（日次データのため）
            last_et_date = last_updated.astimezone(ET).date()
            now_et = now.astimezone(ET)
            if now_et.date() > last_et_date:
                # さらにET 10:00以降であれば更新（OpenTableの更新タイミング想定）
                if now_et.hour >= 10:
                    return True

            return False

        except Exception as e:
            logger.warning(f"[OpenTable] Error checking refresh status: {e}")
            return True

    def _get_latest_info(self) -> Dict[str, Any]:
        """最新データ情報を取得"""
        # 日次データなので、前日のデータが最新
        yesterday = date.today() - timedelta(days=1)
        return {
            "date": yesterday.strftime("%Y-%m-%d"),
            "description": f"Data as of {yesterday.strftime('%b %d, %Y')}"
        }

    def _capture_screenshot(self) -> bool:
        """PlaywrightRunner 経由でチャート要素のスクリーンショットを取得.

        旧 Playwright 直接実装と同等:
            - viewport 1400x1200
            - Cookie banner クローズ (pre_click_selectors)
            - ロード後 5 秒待機
            - 地域セレクタを United States へ + 中央スクロール (pre_screenshot_js)
            - 候補セレクタを順に試して 300x200 以上の要素を要素クリップ
        """
        target_selector = "[data-opentable-target='1']"
        request = ScreenshotRequest(
            url=OPENTABLE_URL,
            output_path=str(self.screenshot_path),
            wait_for_load_state="domcontentloaded",
            wait_after_load_ms=5_000,
            pre_click_selectors=(
                'button:has-text("Accept All")',
                'button:has-text("Accept")',
                'button:has-text("Agree")',
                '#onetrust-accept-btn-handler',
                '[id*="cookie"] button',
                '.cookie-consent button',
            ),
            pre_screenshot_js=self._PRE_SCREENSHOT_JS,
            wait_after_pre_js_ms=3_000,  # チャート再描画を待つ
            clip_selector=target_selector,
            scroll_into_view=True,
            viewport_override=(1400, 1200),
        )
        config = BrowserConfig(
            viewport=(1400, 1200),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        try:
            result = take_screenshot_with_retry(
                request,
                config=config,
                max_attempts=2,
                initial_backoff_seconds=5.0,
            )
            logger.info(
                f"[OpenTable] Chart screenshot saved: {result.path} "
                f"({result.size_bytes} bytes)"
            )
            return True
        except BrowserRunnerError as e:
            logger.error(f"[OpenTable] Screenshot capture failed: {e}")
            return False

    def get_screenshot_base64(self) -> Optional[str]:
        """スクリーンショットをBase64エンコードして返す"""
        if not self.screenshot_path.exists():
            return None

        try:
            with open(self.screenshot_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logger.warning(f"[OpenTable] Error encoding screenshot: {e}")
            return None

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if exists else None
        file_exists = self.screenshot_path.exists()

        return {
            "cache_key": self.CACHE_KEY,
            "cache_exists": exists,
            "file_exists": file_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_path": str(self.screenshot_path)
        }

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)


# シングルトンインスタンス
opentable_service = OpenTableService()
