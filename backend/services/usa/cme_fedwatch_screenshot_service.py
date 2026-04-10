"""
CME FedWatch Tool スクリーンショットサービス

Playwright (BrowserRunner / run_custom_flow) を使用して
CME FedWatch ページのスクリーンショットを取得。
iframe 内の Aggregated テーブルをキャプチャする。
Chromium 失敗時は Firefox にフォールバック。
"""
import logging
import os
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

# 日本時間 (JST = UTC+9)
JST = timezone(timedelta(hours=9))

try:
    from backend.services.browser import BrowserConfig, run_custom_flow
    from backend.services.browser.stale_while_revalidate import background_revalidate
except ImportError:
    from services.browser import BrowserConfig, run_custom_flow
    from services.browser.stale_while_revalidate import background_revalidate

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

# スクリーンショット保存ディレクトリ
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "/app/screenshots"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# CME FedWatch Tool公式ページ
FEDWATCH_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"

# 前環境で使用していたAggregatedテーブルの要素ID
AGGREGATED_TABLE_ID = "ctl00_MainContent_ucViewControl_IntegratedFedWatchTool_uccv_uc1Chart_divChart"


class CMEFedWatchScreenshotService:
    """
    CME FedWatch Tool のスクリーンショットを取得するサービス
    """

    CACHE_KEY = "usa:fedwatch:screenshot"
    CACHE_TTL = 1800  # 30分

    def __init__(self):
        self.screenshot_path = SCREENSHOT_DIR / "fedwatch_latest.png"

    def get_screenshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        FedWatchスクリーンショットを取得

        Stale-While-Revalidate パターン:
        - キャッシュがあれば（古くても）即座に返す
        - Redisキャッシュ期限切れの場合、バックグラウンドで更新を起動
        - force_refresh=True の場合のみ同期で取得

        Returns:
            {
                "image_url": str,
                "last_updated": str,
                "cached": bool
            }
        """
        # 1. キャッシュをチェック
        cached = redis_client.get(self.CACHE_KEY)

        if not force_refresh:
            if cached and self.screenshot_path.exists():
                return {
                    "image_url": f"/static/screenshots/fedwatch_latest.png",
                    "last_updated": cached.get("last_updated"),
                    "cached": True,
                    "source": "redis"
                }

            # Redisキャッシュ切れだがファイルは残っている → SWR
            if self.screenshot_path.exists():
                background_revalidate(
                    f"swr:{self.CACHE_KEY}",
                    self._capture_and_cache,
                )
                return {
                    "image_url": f"/static/screenshots/fedwatch_latest.png",
                    "last_updated": None,
                    "cached": True,
                    "source": "file_swr",
                    "revalidating": True,
                }

        # 2. force_refresh または初回（ファイルなし） → 同期で取得
        success = self._capture_screenshot()

        if success:
            cache_data = {
                "last_updated": datetime.now(JST).isoformat(),
                "path": str(self.screenshot_path)
            }
            redis_client.set(self.CACHE_KEY, cache_data, expire=self.CACHE_TTL)

            return {
                "image_url": f"/static/screenshots/fedwatch_latest.png",
                "last_updated": cache_data["last_updated"],
                "cached": False,
                "source": "playwright"
            }

        # 3. 失敗時は既存のスクリーンショットを返す
        if self.screenshot_path.exists():
            return {
                "image_url": f"/static/screenshots/fedwatch_latest.png",
                "last_updated": None,
                "cached": True,
                "source": "file_stale",
                "error": "Failed to capture new screenshot"
            }

        return {
            "image_url": None,
            "last_updated": None,
            "cached": False,
            "source": "none",
            "error": "No screenshot available"
        }

    def _capture_and_cache(self) -> None:
        """バックグラウンド更新用: スクショ取得 + Redisキャッシュ保存"""
        success = self._capture_screenshot()
        if success:
            cache_data = {
                "last_updated": datetime.now(JST).isoformat(),
                "path": str(self.screenshot_path)
            }
            redis_client.set(self.CACHE_KEY, cache_data, expire=self.CACHE_TTL)
            logger.info("FedWatch screenshot updated via SWR")

    def _capture_screenshot(self) -> bool:
        """
        run_custom_flow 経由でスクリーンショットを取得。
        Chromium が失敗した場合は Firefox にフォールバック。
        """
        if self._capture_with_browser("chromium"):
            return True

        logger.info("Chromium failed, trying Firefox...")
        return self._capture_with_browser("firefox")

    def _capture_with_browser(self, browser_type: str) -> bool:
        """
        run_custom_flow 経由で指定ブラウザでスクリーンショットを取得。
        QuikStrike iframe 内の Aggregated テーブルをキャプチャする。
        """
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
            if browser_type == "firefox"
            else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        config = BrowserConfig(
            viewport=(1920, 1080),
            user_agent=ua,
            default_navigation_timeout_ms=60_000,
        )
        screenshot_path = str(self.screenshot_path)

        def _fedwatch_flow(context) -> bool:
            page = context.new_page()
            try:
                logger.info(f"Capturing FedWatch screenshot with {browser_type}...")
                page.goto(FEDWATCH_URL, wait_until="domcontentloaded")

                # iframe が読み込まれるまで待機
                page.wait_for_timeout(15_000)

                # Cookie 同意バナーを閉じる
                try:
                    cookie_btn = page.locator(
                        'button:has-text("Accept"), button:has-text("Agree"), [id*="onetrust-accept"]'
                    ).first
                    if cookie_btn.is_visible(timeout=3000):
                        cookie_btn.click()
                        page.wait_for_timeout(1000)
                        logger.info("Cookie banner closed")
                except Exception:
                    pass

                screenshot_taken = False

                # iframe を確認
                try:
                    frames = page.frames
                    logger.info(f"Found {len(frames)} frames")
                    for i, frame in enumerate(frames):
                        frame_url = frame.url[:100] if frame.url else "about:blank"
                        logger.debug(f"  Frame {i}: {frame_url}")

                        if "quikstrike" in frame_url.lower() and "IntegratedFedWatchTool" in frame_url:
                            logger.info(f"Found QuikStrike FedWatch iframe: {frame_url[:80]}...")

                            # 「Aggregated」タブをクリック
                            tab_clicked = False
                            aggregated_tab_selectors = [
                                "#ctl00_MainContent_ucViewControl_IntegratedFedWatchTool_uccv_lbAggregate",
                                'a:has-text("Aggregated")',
                                "[id*='lbAggregate']",
                                "text=Aggregated",
                                'span:has-text("Aggregated")',
                            ]
                            for tab_sel in aggregated_tab_selectors:
                                try:
                                    tab = frame.locator(tab_sel).first
                                    if tab.is_visible(timeout=3000):
                                        tab.click()
                                        logger.info(f"Clicked Aggregated tab using: {tab_sel}")
                                        page.wait_for_timeout(4000)
                                        tab_clicked = True
                                        break
                                except Exception as e:
                                    logger.debug(f"  Tab selector {tab_sel} failed: {e}")
                                    continue

                            if not tab_clicked:
                                logger.info("Could not click Aggregated tab, trying to find content anyway...")
                            else:
                                page.wait_for_timeout(2000)

                            # Aggregated テーブルのスクリーンショット
                            table_selectors = [
                                f"#{AGGREGATED_TABLE_ID}",
                                "[id*='uc1Chart_divChart']",
                                "[id*='divChart']",
                                "[id*='Chart_div']",
                            ]
                            for table_sel in table_selectors:
                                try:
                                    aggregated_table = frame.locator(table_sel).first
                                    if aggregated_table.is_visible(timeout=3000):
                                        box = aggregated_table.bounding_box()
                                        if box and box["width"] > 300 and box["height"] > 200:
                                            aggregated_table.screenshot(path=screenshot_path)
                                            logger.info(f"Screenshot saved from iframe using: {table_sel}")
                                            screenshot_taken = True
                                            break
                                except Exception as e:
                                    logger.debug(f"  Table selector {table_sel} failed: {e}")
                                    continue

                            # MEETING DATE テーブルを探す
                            if not screenshot_taken:
                                try:
                                    meeting_date_cell = frame.locator("text=MEETING DATE").first
                                    if meeting_date_cell.is_visible(timeout=3000):
                                        parent_table = frame.locator('table:has(th:has-text("MEETING DATE"))').first
                                        if parent_table.is_visible(timeout=2000):
                                            box = parent_table.bounding_box()
                                            if box and box["width"] > 300 and box["height"] > 200:
                                                parent_table.screenshot(path=screenshot_path)
                                                logger.info("Screenshot saved: Aggregated table with MEETING DATE")
                                                screenshot_taken = True
                                except Exception as e:
                                    logger.debug(f"MEETING DATE table not found: {e}")

                            # 最も縦に長いテーブルを選択
                            if not screenshot_taken:
                                try:
                                    tables = frame.locator("table").all()
                                    logger.info(f"Found {len(tables)} tables in iframe")
                                    best_table = None
                                    best_height = 0
                                    for idx, table in enumerate(tables):
                                        if table.is_visible(timeout=1000):
                                            box = table.bounding_box()
                                            if box:
                                                logger.debug(f"  Table #{idx}: {box['width']:.0f}x{box['height']:.0f}")
                                                if box["height"] > best_height and box["height"] > 400:
                                                    best_height = box["height"]
                                                    best_table = table
                                    if best_table:
                                        best_table.screenshot(path=screenshot_path)
                                        logger.info(f"Screenshot saved: largest table (height={best_height:.0f})")
                                        screenshot_taken = True
                                except Exception as e:
                                    logger.warning(f"Error finding tables: {e}")

                        if screenshot_taken:
                            break
                except Exception as e:
                    logger.warning(f"Error checking frames: {e}")

                # iframe 内で見つからない場合、メインページで探す
                if not screenshot_taken:
                    logger.info("Trying to find FedWatch content in main page...")
                    main_selectors = [
                        '[class*="fedwatch"]', '[class*="FedWatch"]',
                        '[id*="fedwatch"]', '[id*="FedWatch"]',
                        '[class*="probability"]',
                        ".cme-fedwatch-tool", ".tool-container",
                        '[class*="tool-wrapper"]',
                        'iframe[src*="quikstrike"]', 'iframe[src*="fedwatch"]',
                    ]
                    for selector in main_selectors:
                        try:
                            elements = page.locator(selector).all()
                            for element in elements:
                                if element.is_visible(timeout=2000):
                                    box = element.bounding_box()
                                    if box and box["width"] > 400 and box["height"] > 200:
                                        element.screenshot(path=screenshot_path)
                                        logger.info(f"Screenshot saved using main page selector: {selector}")
                                        screenshot_taken = True
                                        break
                        except Exception:
                            continue
                        if screenshot_taken:
                            break

                # 最後の手段: ページ中央部分をクリップ
                if not screenshot_taken:
                    logger.info("Using clip region for main content area...")
                    page.screenshot(
                        path=screenshot_path,
                        clip={"x": 0, "y": 150, "width": 1920, "height": 900},
                    )
                    logger.info(f"Clipped screenshot saved to {screenshot_path}")

                return True
            except Exception as e:
                logger.error(f"Error in FedWatch flow: {e}", exc_info=True)
                return False
            finally:
                try:
                    page.close()
                except Exception:
                    pass

        try:
            result = run_custom_flow(_fedwatch_flow, config=config, browser_type=browser_type)
            return result and self.screenshot_path.exists()
        except Exception as e:
            logger.error(f"Error capturing screenshot with {browser_type}: {e}")
            return False

    def get_screenshot_base64(self) -> Optional[str]:
        """
        スクリーンショットをBase64エンコードして返す
        """
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
        ttl = redis_client.ttl(self.CACHE_KEY) if exists else -1
        file_exists = self.screenshot_path.exists()

        return {
            "cache_key": self.CACHE_KEY,
            "cache_exists": exists,
            "file_exists": file_exists,
            "ttl_seconds": ttl,
            "ttl_minutes": round(ttl / 60, 1) if ttl > 0 else 0,
            "file_path": str(self.screenshot_path)
        }

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)


# シングルトンインスタンス
cme_fedwatch_screenshot_service = CMEFedWatchScreenshotService()
