"""
中国 百度迁徙（Baidu Migration）人流総量 Screenshot Service
百度地图慧眼のチャートのスクリーンショット取得

URL:
- https://qianxi.baidu.com/#/

Target CSS: .mgs-line
スクリーンショット前にJS実行でチャート高さ・凡例位置を調整

[移行ノート]
このサービスは backend.services.browser.PlaywrightRunner 経由に統一済み
(ARM64 / OCI 対応)。以前の Selenium / webdriver_manager / chromium-driver
依存はすべて削除。public API (capture_screenshot / get_screenshot_url /
get_cache_status / invalidate_cache) は完全互換。
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.browser import (
    BrowserConfig,
    BrowserRunnerError,
    ScreenshotRequest,
    take_screenshot_with_retry,
)
from services.browser.stale_while_revalidate import background_revalidate

logger = logging.getLogger(__name__)


JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# スクリーンショットファイル名
SCREENSHOT_FILENAME = "cn_baidu_migration.png"
SCREENSHOT_PATH = CACHE_DIR / SCREENSHOT_FILENAME

# スクリーンショット対象URL
SCREENSHOT_URL = "https://qianxi.baidu.com/#/"

# チャートレイアウト調整用JS
LAYOUT_ADJUST_JS = """
(function() {
    var root = document.querySelector('.mgs-line');
    if (!root) return false;

    // ルート要素: overflow hidden で背景の地図を隠す
    root.style.overflow = 'hidden';
    root.style.height = '500px';
    root.style.position = 'relative';
    root.style.zIndex = '999';
    root.style.backgroundColor = '#242b3a';

    // echarts DOM の高さを拡大
    var chartDom = root.querySelector('[_echarts_instance_]');
    if (chartDom) {
        chartDom.style.height = '430px';
    }

    // 右下のマスコット削除
    var mascot = document.getElementById('floatGuaJian');
    if (mascot) mascot.remove();

    // echarts: 凡例位置調整 + grid拡大 + リサイズ
    if (chartDom && typeof echarts !== 'undefined') {
        var chart = echarts.getInstanceByDom(chartDom);
        if (chart) {
            var option = chart.getOption();
            if (Array.isArray(option.legend)) {
                option.legend.forEach(function(legend) {
                    legend.top = 40;
                });
            }
            if (Array.isArray(option.grid)) {
                option.grid.forEach(function(g) {
                    g.bottom = 40;
                });
            }
            chart.setOption(option);
            chart.resize();
        }
    }

    return true;
})();
"""


class CnBaiduMigrationScreenshotService:
    """China Baidu Migration (人流総量) Screenshot Service"""

    CACHE_KEY = "china:baidu_migration_screenshot:metadata"

    def __init__(self):
        pass

    def _capture_screenshot(self, url: str, output_path: Path) -> bool:
        """Capture screenshot from Baidu Migration page via PlaywrightRunner.

        以前の Selenium 実装と同等の挙動:
            - viewport 1920x1400, locale zh-CN
            - .mgs-line 出現を待ち、追加で 3 秒待機 (canvas 描画のため)
            - LAYOUT_ADJUST_JS をスクショ直前に実行 (凡例位置調整等)
            - .mgs-line を要素クリップでスクショ
        """
        request = ScreenshotRequest(
            url=url,
            output_path=str(output_path),
            wait_selector=".mgs-line",
            wait_for_load_state="networkidle",
            wait_after_load_ms=8_000,  # 旧実装の time.sleep(8) 相当
            clip_selector=".mgs-line",
            scroll_into_view=True,
            pre_screenshot_js=LAYOUT_ADJUST_JS,
            wait_after_pre_js_ms=2_000,  # 旧実装の time.sleep(2) 相当
            viewport_override=(1920, 1400),
        )
        config = BrowserConfig(
            viewport=(1920, 1400),
            locale="zh-CN",
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
                f"[BaiduMigration] screenshot saved: {result.path} "
                f"({result.size_bytes} bytes)"
            )
            return True
        except BrowserRunnerError as e:
            logger.error(f"[BaiduMigration] capture failed: {e}")
            return False

    def capture_screenshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Capture Baidu Migration screenshot"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)

        # キャッシュチェック（24時間）
        if not force_refresh and SCREENSHOT_PATH.exists():
            file_age = now.timestamp() - SCREENSHOT_PATH.stat().st_mtime
            if file_age < 86400:
                print(f"[BaiduMigration] Using cached screenshot (age: {file_age/3600:.1f} hours)")
                return {
                    "success": True,
                    "url": f"/cache/china/economy/{SCREENSHOT_FILENAME}",
                    "cached": True,
                    "last_updated": self._get_last_updated(),
                }
            # SWR: stale cache exists → return it immediately, update in background
            background_revalidate(
                f"swr:{self.CACHE_KEY}",
                lambda: self.capture_screenshot(force_refresh=True),
            )
            return {
                "success": True,
                "url": f"/cache/china/economy/{SCREENSHOT_FILENAME}",
                "cached": True,
                "last_updated": self._get_last_updated(),
                "revalidating": True,
            }

        # スクリーンショット取得
        print("[BaiduMigration] Capturing Baidu Migration screenshot...")
        success = self._capture_screenshot(SCREENSHOT_URL, SCREENSHOT_PATH)

        result = {
            "success": success,
            "url": f"/cache/china/economy/{SCREENSHOT_FILENAME}" if success else None,
            "cached": False,
            "last_updated": now.isoformat(),
        }

        # メタデータをRedisに保存
        redis_client.set(
            self.CACHE_KEY,
            {
                "last_updated": now.isoformat(),
                "screenshot_exists": SCREENSHOT_PATH.exists(),
            },
            expire=0,
        )

        return result

    def get_screenshot_url(self) -> Dict[str, Any]:
        """Get URL for cached screenshot"""
        result = {
            "screenshot_url": None,
            "last_updated": None,
        }

        if SCREENSHOT_PATH.exists():
            result["screenshot_url"] = f"/cache/china/economy/{SCREENSHOT_FILENAME}"

        result["last_updated"] = self._get_last_updated()

        return result

    def _get_last_updated(self) -> str | None:
        """Get last updated timestamp"""
        cached_meta = redis_client.get(self.CACHE_KEY)
        if cached_meta:
            return cached_meta.get("last_updated")

        if SCREENSHOT_PATH.exists():
            mtime = datetime.fromtimestamp(SCREENSHOT_PATH.stat().st_mtime, tz=JST)
            return mtime.isoformat()

        return None

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status"""
        return {
            "indicator": "China Baidu Migration (Total Number of People)",
            "source": "百度地图慧眼",
            "cache_key": self.CACHE_KEY,
            "screenshot_exists": SCREENSHOT_PATH.exists(),
            "last_updated": self._get_last_updated(),
        }

    def invalidate_cache(self) -> bool:
        """Invalidate screenshot cache"""
        redis_client.delete(self.CACHE_KEY)
        return True


# シングルトンインスタンス
cn_baidu_migration_screenshot_service = CnBaiduMigrationScreenshotService()
