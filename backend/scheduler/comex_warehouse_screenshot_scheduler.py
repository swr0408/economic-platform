"""
COMEX 倉庫在庫 (Gold/Silver) スクリーンショット日次スケジューラー

MacroMicro のチャートを毎日 JST 7:00 に自動更新する。
フォールバック: JST 13:00。
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class ComexWarehouseScreenshotScheduler:
    """COMEX 倉庫在庫 スクリーンショット日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service = None

    def _get_service(self):
        if self._service is None:
            try:
                from backend.services.market.comex_warehouse_screenshot_service import (
                    comex_warehouse_screenshot_service,
                )
            except ImportError:
                from services.market.comex_warehouse_screenshot_service import (
                    comex_warehouse_screenshot_service,
                )
            self._service = comex_warehouse_screenshot_service
        return self._service

    async def _run(self):
        try:
            logger.info("[Scheduler] COMEX Warehouse Screenshot: capturing...")
            service = self._get_service()
            result = service.capture_all_screenshots(force_refresh=True)
            gold_ok = result["gold"]["success"]
            silver_ok = result["silver"]["success"]
            copper_ok = result["copper"]["success"]
            logger.info(
                f"[Scheduler] COMEX Warehouse Screenshot: done — "
                f"gold={gold_ok}, silver={silver_ok}, copper={copper_ok}"
            )
        except Exception as e:
            logger.error(
                f"[Scheduler] COMEX Warehouse Screenshot error: {e}",
                exc_info=True,
            )

    def start(self):
        """毎日 JST 7:00 (主) + 13:00 (リトライ) + 起動時キャッチアップ
        スクショファイル mtime が 24h 以上前 or ファイルなしなら即時実行
        """
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=7, minute=0, timezone=JST),
            id="comex_warehouse_screenshot_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=13, minute=0, timezone=JST),
            id="comex_warehouse_screenshot_fallback",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # 起動時キャッチアップ判定: スクショファイル鮮度を見る
        try:
            try:
                from backend.services.market.comex_warehouse_screenshot_service import (
                    GOLD_SCREENSHOT_PATH,
                )
            except ImportError:
                from services.market.comex_warehouse_screenshot_service import (
                    GOLD_SCREENSHOT_PATH,
                )
            should_catchup = True
            if GOLD_SCREENSHOT_PATH.exists():
                age_seconds = datetime.now().timestamp() - GOLD_SCREENSHOT_PATH.stat().st_mtime
                age_hours = age_seconds / 3600
                should_catchup = age_hours >= 24
                logger.info(
                    f"[Scheduler] COMEX Warehouse Screenshot file age: "
                    f"{age_hours:.1f}h"
                )
            if should_catchup:
                self.scheduler.add_job(
                    self._run,
                    "date",
                    run_date=datetime.now(JST) + timedelta(seconds=60),
                    id="comex_warehouse_screenshot_startup_catchup",
                    replace_existing=True,
                    misfire_grace_time=300,
                )
                logger.info(
                    "[Scheduler] COMEX Warehouse Screenshot startup catch-up "
                    "scheduled (in 60s)"
                )
        except Exception as e:
            logger.warning(
                f"[Scheduler] COMEX Warehouse Screenshot startup catch-up "
                f"setup failed: {e}"
            )

        self.scheduler.start()
        logger.info(
            "[Scheduler] COMEX Warehouse Screenshot Scheduler started "
            "(daily JST 7:00, 13:00)"
        )

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


comex_warehouse_screenshot_scheduler = ComexWarehouseScreenshotScheduler()
