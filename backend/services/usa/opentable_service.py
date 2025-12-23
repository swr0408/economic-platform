"""
OpenTable Seated Diners サービス
OpenTableからレストラン予約件数前年比チャートのスクリーンショットを取得

データソース: https://www.opentable.com/state-of-industry

更新スケジュール:
- 毎日更新（米国時間で日次更新、JST 10:00頃を想定）
- 日次データ

キャッシュ方式: last_updated判定（24時間有効、データ更新時に自動リフレッシュ）
"""
import os
import base64
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client


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
            print(f"Error checking refresh status: {e}")
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
        """
        Playwrightを使用してスクリーンショットを取得
        """
        # まずChromiumで試行
        if self._capture_with_browser('chromium'):
            return True

        # Chromiumが失敗した場合はFirefoxで試行
        print("Chromium failed, trying Firefox...")
        return self._capture_with_browser('firefox')

    def _capture_with_browser(self, browser_type: str) -> bool:
        """
        指定されたブラウザでスクリーンショットを取得
        """
        try:
            from playwright.sync_api import sync_playwright

            print(f"Capturing OpenTable chart with {browser_type}...")
            print(f"URL: {OPENTABLE_URL}")

            with sync_playwright() as p:
                # ブラウザを選択
                if browser_type == 'firefox':
                    browser = p.firefox.launch(headless=True)
                else:
                    browser = p.chromium.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu',
                            '--disable-http2',  # HTTP2エラー対策
                        ]
                    )

                # ビューポート設定
                context = browser.new_context(
                    viewport={'width': 1400, 'height': 1200},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )

                page = context.new_page()

                # ページにアクセス（HTTP2エラー対策でwait_untilを変更）
                try:
                    page.goto(OPENTABLE_URL, wait_until='domcontentloaded', timeout=60000)
                except Exception as goto_error:
                    print(f"First goto attempt failed: {goto_error}")
                    # リトライ
                    page.goto(OPENTABLE_URL, wait_until='load', timeout=60000)

                # チャートが読み込まれるまで待機
                page.wait_for_timeout(5000)

                # ページタイトルを確認（デバッグ用）
                print(f"Page title: {page.title()}")

                # Cookie同意バナーを閉じる
                try:
                    cookie_selectors = [
                        'button:has-text("Accept")',
                        'button:has-text("Agree")',
                        'button:has-text("Accept All")',
                        '[id*="cookie"] button',
                        '.cookie-consent button',
                        '#onetrust-accept-btn-handler',
                    ]
                    for selector in cookie_selectors:
                        try:
                            btn = page.locator(selector).first
                            if btn.is_visible(timeout=2000):
                                btn.click()
                                page.wait_for_timeout(1000)
                                print("Cookie banner closed")
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                # 地域セレクタを "United States" に変更
                try:
                    # aria-label="Select location for data" のselect要素を使用
                    geography_selector = page.locator('select[aria-label="Select location for data"]').first

                    if geography_selector.is_visible(timeout=5000):
                        # United States を選択（value="840"）
                        geography_selector.select_option(value="840")
                        page.wait_for_timeout(3000)  # チャート更新を待つ
                        print("Changed geography to United States")
                    else:
                        # フォールバック: すべてのselectを探してUnited Statesオプションがあるものを選択
                        all_selects = page.locator('select').all()
                        for sel in all_selects:
                            try:
                                options = sel.evaluate("el => Array.from(el.options).map(o => o.text)")
                                if 'United States' in options:
                                    sel.select_option(label="United States")
                                    page.wait_for_timeout(3000)
                                    print("Changed geography to United States (fallback)")
                                    break
                            except Exception:
                                continue
                except Exception as e:
                    print(f"Warning: Could not change geography to United States: {e}")

                # Seated Dinersチャートまでスクロール
                try:
                    # seated-dinersセクションへスクロール
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5);")
                    page.wait_for_timeout(2000)
                except Exception:
                    pass

                # チャート要素を探す
                screenshot_taken = False

                # OpenTableのチャートセレクタ
                chart_selectors = [
                    '#seated-diners-chart',
                    '[class*="seated-diners"]',
                    '.r9-soti-controls',
                    '[class*="chart"]',
                    'canvas',
                    '.highcharts-container',
                    '[id*="highcharts"]',
                ]

                for selector in chart_selectors:
                    try:
                        element = page.locator(selector).first
                        if element.is_visible(timeout=3000):
                            box = element.bounding_box()
                            if box and box['width'] > 300 and box['height'] > 200:
                                element.screenshot(path=str(self.screenshot_path))
                                print(f"Chart screenshot saved using: {selector}")
                                screenshot_taken = True
                                break
                    except Exception:
                        continue

                # 要素が見つからない場合はメインコンテンツをキャプチャ
                if not screenshot_taken:
                    print("Chart element not found, capturing main content...")
                    # ヘッダーを除いたメインコンテンツエリア
                    page.screenshot(
                        path=str(self.screenshot_path),
                        clip={
                            'x': 0,
                            'y': 200,
                            'width': 1400,
                            'height': 800
                        }
                    )
                    print(f"Clipped screenshot saved to {self.screenshot_path}")

                browser.close()

            return self.screenshot_path.exists()

        except ImportError:
            print(f"Playwright not installed for {browser_type}")
            return False
        except Exception as e:
            print(f"Error capturing screenshot with {browser_type}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_screenshot_base64(self) -> Optional[str]:
        """スクリーンショットをBase64エンコードして返す"""
        if not self.screenshot_path.exists():
            return None

        try:
            with open(self.screenshot_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"Error encoding screenshot: {e}")
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
