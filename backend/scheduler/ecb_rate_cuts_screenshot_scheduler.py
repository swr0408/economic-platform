"""
ECB Rate Cuts Expectation スクリーンショット日次スケジューラー

MacroMicro のチャートスクリーンショットを毎日 JST 6:00 に自動更新する。
フォールバックとして JST 12:00 にも実行（朝の取得が失敗した場合に備える）。
"""
import logging
from zoneinfo import ZoneInfo

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class ECBRateCutsScreenshotScheduler:
    """ECB Rate Cuts スクリーンショット日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service = None

    def _get_service(self):
        if self._service is None:
            try:
                from backend.services.eurozone.ecb_rate_cuts_screenshot_service import (
                    ecb_rate_cuts_screenshot_service,
                )
            except ImportError:
                from services.eurozone.ecb_rate_cuts_screenshot_service import (
                    ecb_rate_cuts_screenshot_service,
                )
            self._service = ecb_rate_cuts_screenshot_service
        return self._service

    async def _run(self):
        """スクリーンショットを強制更新"""
        try:
            logger.info("[Scheduler] ECB RateCuts Screenshot: capturing...")
            service = self._get_service()
            # Playwright sync API はブロッキング。ワーカースレッドへ退避しないと
            # イベントループを占有し login 等すべてのエンドポイントが落ちる。
            result = await asyncio.to_thread(service.capture_all_screenshots, force_refresh=True)
            yearend_ok = result["yearend"]["success"]
            rate_cuts_ok = result["rate_cuts"]["success"]
            logger.info(
                f"[Scheduler] ECB RateCuts Screenshot: done — "
                f"yearend={yearend_ok}, rate_cuts={rate_cuts_ok}"
            )
        except Exception as e:
            logger.error(
                f"[Scheduler] ECB RateCuts Screenshot error: {e}",
                exc_info=True,
            )

    def start(self):
        """スケジューラーを開始（毎日 JST 6:00, 12:00）"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=6, minute=0, timezone=JST),
            id="ecb_rate_cuts_screenshot_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=12, minute=0, timezone=JST),
            id="ecb_rate_cuts_screenshot_fallback",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info(
            "[Scheduler] ECB RateCuts Screenshot Scheduler started "
            "(daily JST 6:00, 12:00)"
        )

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


ecb_rate_cuts_screenshot_scheduler = ECBRateCutsScreenshotScheduler()
