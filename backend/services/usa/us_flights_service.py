"""
米国航空機便数（US Flights）サービス
Airportiaからフライトモニターチャートのスクリーンショットを取得

データソース: https://www.airportia.com/flights-monitor/?country=US

更新スケジュール:
- 毎日1回更新（UTC 06:00 = JST 15:00）
- 日次データなので頻繁な更新は不要

キャッシュ方式: last_updated判定（24時間有効）

[移行ノート]
このサービスは backend.services.browser.PlaywrightRunner 経由に統一済み
(ARM64 / OCI 対応)。以前の Playwright 直接利用はすべて削除。
旧実装の「複数候補セレクタを順に試して最初に見つかったチャート要素を
要素スクショ」ロジックを `pre_screenshot_js` でブラウザ内に再現し、
対象要素に data-us-flights-target="1" 属性を付与した上で
`clip_selector` で要素クリップする。
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

# スクリーンショット保存ディレクトリ
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "/app/screenshots"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Airportia フライトモニターURL
AIRPORTIA_URL = "https://www.airportia.com/flights-monitor/?country=US"


class USFlightsService:
    """
    米国航空機便数サービス
    Airportiaからフライトモニターチャートのスクリーンショットを取得
    """

    CACHE_KEY = "usa:flights:screenshot"
    SCHEDULE_CACHE_KEY = "usa:flights:schedule"
    # キャッシュTTL: 24時間（日次データ）
    CACHE_TTL = 24 * 60 * 60  # 86400秒

    # 旧 Playwright 実装 (複数候補セレクタを順に試して最初に見つかった
    # 300x200 以上のチャート要素を採用) をブラウザ内 JS で再現する。
    # 対象要素には data-us-flights-target="1" 属性を付与し、
    # ScreenshotRequest.clip_selector でそれをクリップする。
    _PRE_SCREENSHOT_JS = r"""
    (() => {
      const selectors = [
        '#chart',
        '.flight-chart',
        '[class*="chart"]',
        'canvas',
        '.highcharts-container',
        '[id*="highcharts"]',
        '.chart-container',
      ];
      // 既存タグを掃除
      document.querySelectorAll('[data-us-flights-target]')
        .forEach(el => el.removeAttribute('data-us-flights-target'));
      for (const sel of selectors) {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
          const r = el.getBoundingClientRect();
          if (r.width > 300 && r.height > 200) {
            el.setAttribute('data-us-flights-target', '1');
            el.scrollIntoView({block: 'center'});
            return true;
          }
        }
      }
      return false;
    })();
    """

    def __init__(self):
        self.screenshot_path = SCREENSHOT_DIR / "us_flights_chart.png"

    def get_flights_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        フライトチャートデータを取得

        Returns:
            {
                "image_url": str,  # 画像へのパス
                "latest": {"date": str, "description": str},
                "next_update": {"date": str, "label": str},
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
                        "image_url": "/static/screenshots/us_flights_chart.png",
                        "latest": self._get_latest_info(),
                        "next_update": self._get_next_update(),
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
                    "image_url": "/static/screenshots/us_flights_chart.png",
                    "latest": self._get_latest_info(),
                    "next_update": self._get_next_update(),
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
                "image_url": "/static/screenshots/us_flights_chart.png",
                "latest": self._get_latest_info(),
                "next_update": self._get_next_update(),
                "last_updated": cache_data["last_updated"],
                "cached": False,
                "source": "playwright"
            }

        # 4. 失敗時は既存のスクリーンショットを返す
        if self.screenshot_path.exists():
            return {
                "image_url": "/static/screenshots/us_flights_chart.png",
                "latest": self._get_latest_info(),
                "next_update": self._get_next_update(),
                "last_updated": None,
                "cached": True,
                "source": "file_stale",
                "error": "Failed to capture new screenshot"
            }

        return {
            "image_url": None,
            "latest": None,
            "next_update": self._get_next_update(),
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
        - または、UTCで日付が変わっていれば更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 24時間経過していれば更新
            if (now - last_updated).total_seconds() >= self.CACHE_TTL:
                return True

            # UTC日付が変わっていれば更新（日次データのため）
            last_utc_date = last_updated.astimezone(UTC).date()
            now_utc_date = now.astimezone(UTC).date()
            if now_utc_date > last_utc_date:
                # さらにUTC 06:00以降であれば更新（Airportiaの更新タイミング）
                utc_now = now.astimezone(UTC)
                if utc_now.hour >= 6:
                    return True

            return False

        except Exception as e:
            logger.warning(f"[USFlights] Error checking refresh status: {e}")
            return True

    def _get_latest_info(self) -> Dict[str, Any]:
        """最新データ情報を取得"""
        # 日次データなので、前日のデータが最新
        yesterday = date.today() - timedelta(days=1)
        return {
            "date": yesterday.strftime("%Y-%m-%d"),
            "description": f"Data as of {yesterday.strftime('%b %d, %Y')}"
        }

    def _get_next_update(self) -> Dict[str, Any]:
        """次回更新予定を取得"""
        now = datetime.now(UTC)

        # 次のUTC 06:00を計算
        if now.hour >= 6:
            # 今日のUTC 06:00を過ぎている → 明日のUTC 06:00
            next_update = (now + timedelta(days=1)).replace(
                hour=6, minute=0, second=0, microsecond=0
            )
        else:
            # まだUTC 06:00前 → 今日のUTC 06:00
            next_update = now.replace(hour=6, minute=0, second=0, microsecond=0)

        # JSTに変換
        next_update_jst = next_update.astimezone(JST)

        return {
            "date": next_update_jst.strftime("%Y-%m-%d"),
            "time_jst": next_update_jst.strftime("%H:%M"),
            "label": f"Next update: {next_update_jst.strftime('%b %d, %Y %H:%M')} JST"
        }

    def _capture_screenshot(self) -> bool:
        """PlaywrightRunner 経由でチャート要素のスクリーンショットを取得.

        旧 Playwright 直接実装と同等:
            - viewport 1400x900
            - Cookie banner クローズ (pre_click_selectors)
            - ロード後 5 秒待機 (チャート描画用)
            - 候補セレクタを順に試して 300x200 以上の要素を検出
            - クリップで要素スクショ
        """
        target_selector = "[data-us-flights-target='1']"
        request = ScreenshotRequest(
            url=AIRPORTIA_URL,
            output_path=str(self.screenshot_path),
            wait_for_load_state="networkidle",
            wait_after_load_ms=5_000,
            pre_click_selectors=(
                'button:has-text("Accept")',
                'button:has-text("Agree")',
                '[id*="cookie"] button',
                '.cookie-consent button',
            ),
            pre_screenshot_js=self._PRE_SCREENSHOT_JS,
            wait_after_pre_js_ms=1_000,
            clip_selector=target_selector,
            scroll_into_view=True,
            viewport_override=(1400, 900),
        )
        config = BrowserConfig(
            viewport=(1400, 900),
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
                f"[USFlights] Chart screenshot saved: {result.path} "
                f"({result.size_bytes} bytes)"
            )
            return True
        except BrowserRunnerError as e:
            logger.error(f"[USFlights] Screenshot capture failed: {e}")
            return False

    def get_screenshot_base64(self) -> Optional[str]:
        """スクリーンショットをBase64エンコードして返す"""
        if not self.screenshot_path.exists():
            return None

        try:
            with open(self.screenshot_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logger.warning(f"[USFlights] Error encoding screenshot: {e}")
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
            "file_path": str(self.screenshot_path),
            "next_update": self._get_next_update()
        }

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)


# シングルトンインスタンス
us_flights_service = USFlightsService()
