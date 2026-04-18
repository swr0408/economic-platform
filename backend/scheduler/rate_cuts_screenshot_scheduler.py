"""
Fed / BOE / BOJ Rate Cuts Expectation スクリーンショット日次スケジューラー

MacroMicro のチャートスクリーンショットを毎日 JST 6:00 に自動更新する。
フォールバックとして JST 12:00 にも実行（朝の取得が失敗した場合に備える）。
"""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class RateCutsScreenshotScheduler:
    """Fed / BOE / BOJ Rate Cuts スクリーンショット日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._fed_service = None
        self._boe_service = None
        self._boj_service = None

    def _get_fed_service(self):
        if self._fed_service is None:
            try:
                from backend.services.usa.fed_rate_cuts_screenshot_service import (
                    fed_rate_cuts_screenshot_service,
                )
            except ImportError:
                from services.usa.fed_rate_cuts_screenshot_service import (
                    fed_rate_cuts_screenshot_service,
                )
            self._fed_service = fed_rate_cuts_screenshot_service
        return self._fed_service

    def _get_boe_service(self):
        if self._boe_service is None:
            try:
                from backend.services.uk.boe_rate_cuts_screenshot_service import (
                    boe_rate_cuts_screenshot_service,
                )
            except ImportError:
                from services.uk.boe_rate_cuts_screenshot_service import (
                    boe_rate_cuts_screenshot_service,
                )
            self._boe_service = boe_rate_cuts_screenshot_service
        return self._boe_service

    def _get_boj_service(self):
        if self._boj_service is None:
            try:
                from backend.services.japan.boj_rate_cuts_screenshot_service import (
                    boj_rate_cuts_screenshot_service,
                )
            except ImportError:
                from services.japan.boj_rate_cuts_screenshot_service import (
                    boj_rate_cuts_screenshot_service,
                )
            self._boj_service = boj_rate_cuts_screenshot_service
        return self._boj_service

    async def _run(self):
        """スクリーンショットを強制更新（Fed + BOE + BOJ）"""
        for label, get_svc in [
            ("Fed", self._get_fed_service),
            ("BOE", self._get_boe_service),
            ("BOJ", self._get_boj_service),
        ]:
            try:
                logger.info(f"[Scheduler] {label} RateCuts Screenshot: capturing...")
                service = get_svc()
                result = service.capture_all_screenshots(force_refresh=True)
                yearend_ok = result["yearend"]["success"]
                rate_cuts_ok = result["rate_cuts"]["success"]
                logger.info(
                    f"[Scheduler] {label} RateCuts Screenshot: done — "
                    f"yearend={yearend_ok}, rate_cuts={rate_cuts_ok}"
                )
            except Exception as e:
                logger.error(
                    f"[Scheduler] {label} RateCuts Screenshot error: {e}",
                    exc_info=True,
                )

    def start(self):
        """スケジューラーを開始（毎日 JST 6:00, 12:00）"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=6, minute=0, timezone=JST),
            id="rate_cuts_screenshot_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=12, minute=0, timezone=JST),
            id="rate_cuts_screenshot_fallback",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info(
            "[Scheduler] Rate Cuts Screenshot Scheduler started "
            "(Fed/BOE/BOJ, daily JST 6:00, 12:00)"
        )

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


rate_cuts_screenshot_scheduler = RateCutsScreenshotScheduler()
