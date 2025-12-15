"""
CME FedWatch Tool スクリーンショットサービス
Playwrightを使用してCME FedWatchページのスクリーンショットを取得
"""
import os
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

# 日本時間 (JST = UTC+9)
JST = timezone(timedelta(hours=9))

from core.redis_client import redis_client

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

        Returns:
            {
                "image_url": str,  # 画像へのパス
                "image_base64": str,  # Base64エンコードされた画像（オプション）
                "last_updated": str,
                "cached": bool
            }
        """
        # 1. キャッシュをチェック
        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY)
            if cached and self.screenshot_path.exists():
                return {
                    "image_url": f"/static/screenshots/fedwatch_latest.png",
                    "last_updated": cached.get("last_updated"),
                    "cached": True,
                    "source": "redis"
                }

        # 2. 新しいスクリーンショットを取得
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

    def _capture_screenshot(self) -> bool:
        """
        Playwrightを使用してスクリーンショットを取得
        Chromiumが失敗した場合はFirefoxにフォールバック
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
        QuikStrikeページの特定要素（チャート）のみをキャプチャ
        """
        try:
            from playwright.sync_api import sync_playwright

            print(f"Capturing FedWatch screenshot with {browser_type}...")
            print(f"URL: {FEDWATCH_URL}")

            with sync_playwright() as p:
                # ブラウザを選択
                if browser_type == 'firefox':
                    browser = p.firefox.launch(
                        headless=True,
                    )
                else:
                    browser = p.chromium.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu',
                        ]
                    )

                # ビューポート設定
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0' if browser_type == 'firefox' else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                )

                page = context.new_page()

                # ページにアクセス（domcontentloadedで待機し、その後追加で待つ）
                page.goto(FEDWATCH_URL, wait_until='domcontentloaded', timeout=60000)

                # iframeが読み込まれるまで待機
                page.wait_for_timeout(15000)

                # Cookie同意バナーを閉じる（存在する場合）
                try:
                    cookie_btn = page.locator('button:has-text("Accept"), button:has-text("Agree"), [id*="onetrust-accept"]').first
                    if cookie_btn.is_visible(timeout=3000):
                        cookie_btn.click()
                        page.wait_for_timeout(1000)
                        print("Cookie banner closed")
                except Exception:
                    pass

                # スクリーンショット取得
                screenshot_taken = False

                # iframeを確認
                try:
                    frames = page.frames
                    print(f"Found {len(frames)} frames")
                    for i, frame in enumerate(frames):
                        frame_url = frame.url[:100] if frame.url else 'about:blank'
                        print(f"  Frame {i}: {frame_url}")

                        # QuikStrike iframe内でAggregatedテーブルを探す
                        if 'quikstrike' in frame_url.lower() and 'IntegratedFedWatchTool' in frame_url:
                            print(f"Found QuikStrike FedWatch iframe: {frame_url[:80]}...")
                            try:
                                # iframe内の全ての要素を確認
                                print("Looking for Aggregated tab in iframe...")

                                # 「Aggregated」タブをクリック
                                tab_clicked = False
                                aggregated_tab_selectors = [
                                    '#ctl00_MainContent_ucViewControl_IntegratedFedWatchTool_uccv_lbAggregate',
                                    'a:has-text("Aggregated")',
                                    '[id*="lbAggregate"]',
                                    'text=Aggregated',
                                    'span:has-text("Aggregated")',
                                ]
                                for tab_sel in aggregated_tab_selectors:
                                    try:
                                        tab = frame.locator(tab_sel).first
                                        if tab.is_visible(timeout=3000):
                                            tab.click()
                                            print(f"Clicked Aggregated tab using: {tab_sel}")
                                            page.wait_for_timeout(4000)  # タブ切り替え後の描画を待つ
                                            tab_clicked = True
                                            break
                                    except Exception as e:
                                        print(f"  Tab selector {tab_sel} failed: {e}")
                                        continue

                                if not tab_clicked:
                                    print("Could not click Aggregated tab, trying to find content anyway...")
                                else:
                                    # タブクリック後、さらに待機してコンテンツ更新を待つ
                                    page.wait_for_timeout(2000)

                                # Aggregatedテーブルのスクリーンショットを取得
                                # まずテーブル全体を含むdivを探す
                                table_selectors = [
                                    f'#{AGGREGATED_TABLE_ID}',
                                    '[id*="uc1Chart_divChart"]',
                                    '[id*="divChart"]',
                                    '[id*="Chart_div"]',
                                ]

                                for table_sel in table_selectors:
                                    try:
                                        aggregated_table = frame.locator(table_sel).first
                                        if aggregated_table.is_visible(timeout=3000):
                                            box = aggregated_table.bounding_box()
                                            if box and box['width'] > 300 and box['height'] > 200:
                                                aggregated_table.screenshot(path=str(self.screenshot_path))
                                                print(f"Screenshot saved from iframe using: {table_sel}")
                                                screenshot_taken = True
                                                break
                                    except Exception as e:
                                        print(f"  Table selector {table_sel} failed: {e}")
                                        continue

                                # まだ見つからない場合、Aggregatedテーブル（MEETING DATEを含むテーブル）を探す
                                if not screenshot_taken:
                                    print("Looking for Aggregated table with MEETING DATE...")
                                    try:
                                        # MEETING DATEヘッダーを含むテーブルを探す（Aggregatedテーブルの特徴）
                                        meeting_date_cell = frame.locator('text=MEETING DATE').first
                                        if meeting_date_cell.is_visible(timeout=3000):
                                            # 親テーブル要素を探す
                                            parent_table = frame.locator('table:has(th:has-text("MEETING DATE"))').first
                                            if parent_table.is_visible(timeout=2000):
                                                box = parent_table.bounding_box()
                                                if box and box['width'] > 300 and box['height'] > 200:
                                                    parent_table.screenshot(path=str(self.screenshot_path))
                                                    print(f"Screenshot saved: Aggregated table with MEETING DATE")
                                                    screenshot_taken = True
                                    except Exception as e:
                                        print(f"MEETING DATE table not found: {e}")

                                # それでも見つからない場合、最も縦に長いテーブルを選択
                                if not screenshot_taken:
                                    print("Looking for largest table...")
                                    try:
                                        tables = frame.locator('table').all()
                                        print(f"Found {len(tables)} tables in iframe")
                                        best_table = None
                                        best_height = 0
                                        for idx, table in enumerate(tables):
                                            if table.is_visible(timeout=1000):
                                                box = table.bounding_box()
                                                if box:
                                                    print(f"  Table #{idx}: {box['width']:.0f}x{box['height']:.0f}")
                                                    # Aggregatedテーブルは縦長（height > 400）のはず
                                                    if box['height'] > best_height and box['height'] > 400:
                                                        best_height = box['height']
                                                        best_table = table
                                        if best_table:
                                            best_table.screenshot(path=str(self.screenshot_path))
                                            print(f"Screenshot saved: largest table (height={best_height:.0f})")
                                            screenshot_taken = True
                                    except Exception as e:
                                        print(f"Error finding tables: {e}")
                            except Exception as e:
                                print(f"Error finding Aggregated table in iframe: {e}")
                        if screenshot_taken:
                            break
                except Exception as e:
                    print(f"Error checking frames: {e}")

                # iframe内で見つからない場合、メインページでFedWatchコンテンツを探す
                if not screenshot_taken:
                    print("Trying to find FedWatch content in main page...")

                    # CME FedWatch Tool専用のセレクタ
                    main_selectors = [
                        # FedWatch Tool埋め込みコンテナ
                        '[class*="fedwatch"]',
                        '[class*="FedWatch"]',
                        '[id*="fedwatch"]',
                        '[id*="FedWatch"]',
                        # 確率テーブル
                        '[class*="probability"]',
                        # ツール全体のコンテナ
                        '.cme-fedwatch-tool',
                        '.tool-container',
                        '[class*="tool-wrapper"]',
                        # iframe自体
                        'iframe[src*="quikstrike"]',
                        'iframe[src*="fedwatch"]',
                    ]

                    for selector in main_selectors:
                        try:
                            elements = page.locator(selector).all()
                            for element in elements:
                                if element.is_visible(timeout=2000):
                                    box = element.bounding_box()
                                    if box and box['width'] > 400 and box['height'] > 200:
                                        element.screenshot(path=str(self.screenshot_path))
                                        print(f"Screenshot saved using main page selector: {selector}")
                                        screenshot_taken = True
                                        break
                        except Exception:
                            continue
                        if screenshot_taken:
                            break

                # ページの中央部分をクリップしてキャプチャ（最後の手段）
                if not screenshot_taken:
                    print("Using clip region for main content area...")
                    # ヘッダーとフッターを除いた中央部分をキャプチャ
                    page.screenshot(
                        path=str(self.screenshot_path),
                        clip={
                            'x': 0,
                            'y': 150,  # ヘッダーをスキップ
                            'width': 1920,
                            'height': 900  # メインコンテンツエリア
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
