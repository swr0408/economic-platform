"""
COMEX 倉庫在庫 (Gold / Silver / Copper) スクリーンショットサービス

CME Group 公式XLSがIPブロックされているため、MacroMicro のチャートを
スクリーンショットで取得して代替表示する。

URLs:
- Gold:   https://en.macromicro.me/series/17518/gold-comex-warehouse-stock
- Silver: https://en.macromicro.me/series/17517/silver-comex-warehouse-stock
- Copper: https://en.macromicro.me/series/8742/copper-comex-warehouse-stock

Target: .mm-cc-bd .container.chart-theater.is-stat
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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

GOLD_SCREENSHOT_FILENAME = "comex_gold_warehouse_stock.png"
SILVER_SCREENSHOT_FILENAME = "comex_silver_warehouse_stock.png"
COPPER_SCREENSHOT_FILENAME = "comex_copper_warehouse_stock.png"

GOLD_SCREENSHOT_PATH = CACHE_DIR / GOLD_SCREENSHOT_FILENAME
SILVER_SCREENSHOT_PATH = CACHE_DIR / SILVER_SCREENSHOT_FILENAME
COPPER_SCREENSHOT_PATH = CACHE_DIR / COPPER_SCREENSHOT_FILENAME

GOLD_URL = "https://www.macromicro.me/series/17518/gold-comex-warehouse-stock"
SILVER_URL = "https://www.macromicro.me/series/17517/silver-comex-warehouse-stock"
COPPER_URL = "https://www.macromicro.me/series/8742/copper-comex-warehouse-stock"


class ComexWarehouseScreenshotService:
    """COMEX Gold/Silver 倉庫在庫 スクリーンショットサービス"""

    CACHE_KEY = "market:comex_warehouse_screenshot:metadata"

    TARGET_SELECTOR = ".mm-cc-bd .container.chart-theater.is-stat"

    def _build_request(self, url: str, output_path: Path) -> ScreenshotRequest:
        # MacroMicro は Cloudflare チャレンジを挟むことがあるため wait_selector は使わず
        # wait_after_load_ms でチャート描画を待つ (cn_credit_impulse と同方式)
        return ScreenshotRequest(
            url=url,
            output_path=str(output_path),
            wait_for_load_state="domcontentloaded",
            # Cloudflare チャレンジ完了を待つ (20~25 秒)
            wait_after_load_ms=25_000,
            wait_selector=self.TARGET_SELECTOR,
            clip_selector=self.TARGET_SELECTOR,
            scroll_into_view=True,
            viewport_override=(1920, 1400),
        )

    def _build_config(self) -> BrowserConfig:
        return BrowserConfig(
            viewport=(1920, 1400),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

    def capture_all_screenshots(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Gold / Silver / Copper の MacroMicro チャートを 1 ブラウザで連続撮影"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.now(JST)
        results: Dict[str, Any] = {
            "gold": {"success": False, "url": None, "cached": False},
            "silver": {"success": False, "url": None, "cached": False},
            "copper": {"success": False, "url": None, "cached": False},
            "last_updated": None,
        }

        items = [
            ("gold", GOLD_URL, GOLD_SCREENSHOT_PATH, GOLD_SCREENSHOT_FILENAME),
            ("silver", SILVER_URL, SILVER_SCREENSHOT_PATH, SILVER_SCREENSHOT_FILENAME),
            ("copper", COPPER_URL, COPPER_SCREENSHOT_PATH, COPPER_SCREENSHOT_FILENAME),
        ]

        # キャッシュ判定 (24h)
        to_capture: list[tuple[str, str, Path, str]] = []
        for key, url, path, filename in items:
            if not force_refresh and path.exists():
                file_age = now.timestamp() - path.stat().st_mtime
                if file_age < 86400:
                    results[key] = {
                        "success": True,
                        "url": f"/cache/market/{filename}",
                        "cached": True,
                    }
                    logger.info(
                        f"[ComexWarehouse] Using cached {key} screenshot "
                        f"(age: {file_age/3600:.1f} hours)"
                    )
                    continue
            to_capture.append((key, url, path, filename))

        if not to_capture:
            cached_meta = redis_client.get(self.CACHE_KEY)
            results["last_updated"] = (
                cached_meta.get("last_updated") if cached_meta else now.isoformat()
            )
            return results

        # SWR: 全ファイル存在 (古い) かつ強制更新でない → 古いURLを即返し、裏で再取得
        all_files_exist = all(path.exists() for _, _, path, _ in to_capture)
        if all_files_exist and not force_refresh:
            for key, url, path, filename in to_capture:
                results[key] = {
                    "success": True,
                    "url": f"/cache/market/{filename}",
                    "cached": True,
                }
            cached_meta = redis_client.get(self.CACHE_KEY)
            results["last_updated"] = (
                cached_meta.get("last_updated") if cached_meta else now.isoformat()
            )
            results["revalidating"] = True
            background_revalidate(
                f"swr:{self.CACHE_KEY}",
                lambda: self.capture_all_screenshots(force_refresh=True),
            )
            return results

        # 各 URL ごとに独立したブラウザセッション + リトライ
        # (連続ナビゲーションだと Cloudflare 再チャレンジに引っかかるため)
        config = self._build_config()
        for key, url, path, filename in to_capture:
            try:
                logger.info(f"[ComexWarehouse] Capturing {key}...")
                result = take_screenshot_with_retry(
                    self._build_request(url, path),
                    config=config,
                    max_attempts=2,
                    initial_backoff_seconds=5.0,
                )
                logger.info(
                    f"[ComexWarehouse] saved {key}: "
                    f"{result.path} ({result.size_bytes} bytes)"
                )
                results[key] = {
                    "success": True,
                    "url": f"/cache/market/{filename}",
                    "cached": False,
                }
            except BrowserRunnerError as e:
                logger.error(f"[ComexWarehouse] {key} capture failed: {e}")
                results[key] = {
                    "success": False,
                    "url": None,
                    "cached": False,
                }

        results["last_updated"] = now.isoformat()

        redis_client.set(self.CACHE_KEY, {
            "last_updated": now.isoformat(),
            "gold_exists": GOLD_SCREENSHOT_PATH.exists(),
            "silver_exists": SILVER_SCREENSHOT_PATH.exists(),
            "copper_exists": COPPER_SCREENSHOT_PATH.exists(),
        }, expire=0)

        return results

    def get_screenshot_urls(self) -> Dict[str, Any]:
        """キャッシュ済みスクリーンショットのURLを取得"""
        result = {
            "gold_url": None,
            "silver_url": None,
            "copper_url": None,
            "last_updated": None,
        }

        if GOLD_SCREENSHOT_PATH.exists():
            result["gold_url"] = f"/cache/market/{GOLD_SCREENSHOT_FILENAME}"
        if SILVER_SCREENSHOT_PATH.exists():
            result["silver_url"] = f"/cache/market/{SILVER_SCREENSHOT_FILENAME}"
        if COPPER_SCREENSHOT_PATH.exists():
            result["copper_url"] = f"/cache/market/{COPPER_SCREENSHOT_FILENAME}"

        cached_meta = redis_client.get(self.CACHE_KEY)
        if cached_meta:
            result["last_updated"] = cached_meta.get("last_updated")
        elif GOLD_SCREENSHOT_PATH.exists():
            mtime = datetime.fromtimestamp(GOLD_SCREENSHOT_PATH.stat().st_mtime, tz=JST)
            result["last_updated"] = mtime.isoformat()

        return result

    def get_cache_status(self) -> Dict[str, Any]:
        cached_meta = redis_client.get(self.CACHE_KEY)
        return {
            "indicator": "COMEX Warehouse Stock Screenshots (Gold/Silver/Copper)",
            "source": "MacroMicro",
            "cache_key": self.CACHE_KEY,
            "gold_exists": GOLD_SCREENSHOT_PATH.exists(),
            "silver_exists": SILVER_SCREENSHOT_PATH.exists(),
            "copper_exists": COPPER_SCREENSHOT_PATH.exists(),
            "last_updated": cached_meta.get("last_updated") if cached_meta else None,
        }

    def invalidate_cache(self) -> bool:
        redis_client.delete(self.CACHE_KEY)
        return True


comex_warehouse_screenshot_service = ComexWarehouseScreenshotService()
