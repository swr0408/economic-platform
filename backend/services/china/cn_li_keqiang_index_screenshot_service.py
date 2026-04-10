"""
中国 李克強指数（Li Keqiang Index）Screenshot Service
MacroMicro のチャートのスクリーンショット取得

URL:
- https://en.macromicro.me/series/28284/china-keqiang-index-new

Target CSS: .mm-cc-bd .container.chart-theater.is-stat

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
SCREENSHOT_FILENAME = "cn_li_keqiang_index.png"
SCREENSHOT_PATH = CACHE_DIR / SCREENSHOT_FILENAME

# スクリーンショット対象URL
SCREENSHOT_URL = "https://en.macromicro.me/series/28284/china-keqiang-index-new"


class CnLiKeqiangIndexScreenshotService:
    """China Li Keqiang Index Screenshot Service"""

    CACHE_KEY = "china:li_keqiang_index_screenshot:metadata"

    def __init__(self):
        pass

    def _capture_screenshot(self, url: str, output_path: Path) -> bool:
        """Capture screenshot from MacroMicro chart page via PlaywrightRunner.

        以前の Selenium 実装と同等の挙動:
            - viewport 1920x1400
            - .mm-cc-bd .container.chart-theater.is-stat 出現を待ち
              追加で計 5 秒待機 (描画完了用)
            - 対象要素に scrollIntoView してから要素クリップでスクショ
        """
        target_selector = ".mm-cc-bd .container.chart-theater.is-stat"
        request = ScreenshotRequest(
            url=url,
            output_path=str(output_path),
            wait_selector=target_selector,
            wait_for_load_state="networkidle",
            wait_after_load_ms=5_000,  # 旧実装の time.sleep(3) + α
            clip_selector=target_selector,
            scroll_into_view=True,
            viewport_override=(1920, 1400),
        )
        config = BrowserConfig(
            viewport=(1920, 1400),
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
                f"[LiKeqiangIndex] screenshot saved: {result.path} "
                f"({result.size_bytes} bytes)"
            )
            return True
        except BrowserRunnerError as e:
            logger.error(f"[LiKeqiangIndex] capture failed: {e}")
            return False

    def capture_screenshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Capture Li Keqiang Index screenshot"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)

        # キャッシュチェック（24時間）
        if not force_refresh and SCREENSHOT_PATH.exists():
            file_age = now.timestamp() - SCREENSHOT_PATH.stat().st_mtime
            if file_age < 86400:
                print(f"[LiKeqiangIndex] Using cached screenshot (age: {file_age/3600:.1f} hours)")
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
        print("[LiKeqiangIndex] Capturing Li Keqiang Index screenshot...")
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
            "indicator": "China Li Keqiang Index Screenshot",
            "source": "MacroMicro",
            "cache_key": self.CACHE_KEY,
            "screenshot_exists": SCREENSHOT_PATH.exists(),
            "last_updated": self._get_last_updated(),
        }

    def invalidate_cache(self) -> bool:
        """Invalidate screenshot cache"""
        redis_client.delete(self.CACHE_KEY)
        return True


# シングルトンインスタンス
cn_li_keqiang_index_screenshot_service = CnLiKeqiangIndexScreenshotService()
