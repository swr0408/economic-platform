"""
ECB Rate Cuts Expectation Screenshot Scheduler
Automatically updates screenshots daily at 2:00 AM JST
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


JST = ZoneInfo("Asia/Tokyo")


class ECBRateCutsScreenshotScheduler:
    """Scheduler for ECB rate cuts expectation screenshot updates"""

    def __init__(self, shared_scheduler: AsyncIOScheduler = None):
        """
        Initialize ECB rate cuts screenshot scheduler

        Args:
            shared_scheduler: Shared APScheduler instance (optional)
        """
        self.scheduler = shared_scheduler
        self._owns_scheduler = shared_scheduler is None

        if self._owns_scheduler:
            self.scheduler = AsyncIOScheduler(timezone=JST)

    async def update_screenshots(self):
        """
        Update ECB rate cuts expectation screenshots
        Runs daily at 2:00 AM JST
        """
        try:
            from services.eurozone.ecb_rate_cuts_screenshot_service import ecb_rate_cuts_screenshot_service

            print(f"[ECBRateCutsScreenshotScheduler] Starting screenshot update at {datetime.now(JST).isoformat()}")

            result = ecb_rate_cuts_screenshot_service.capture_all_screenshots(force_refresh=True)

            if result["yearend"]["success"] and result["rate_cuts"]["success"]:
                print("[ECBRateCutsScreenshotScheduler] Successfully updated all screenshots")
            else:
                if not result["yearend"]["success"]:
                    print("[ECBRateCutsScreenshotScheduler] Failed to update yearend screenshot")
                if not result["rate_cuts"]["success"]:
                    print("[ECBRateCutsScreenshotScheduler] Failed to update rate_cuts screenshot")

        except Exception as e:
            print(f"[ECBRateCutsScreenshotScheduler] Error updating screenshots: {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """Start the ECB rate cuts screenshot scheduler"""
        try:
            # Schedule to run daily at 2:00 AM JST
            self.scheduler.add_job(
                self.update_screenshots,
                CronTrigger(hour=2, minute=0, timezone=JST),
                id='ecb_rate_cuts_screenshot_update',
                name='ECB Rate Cuts Screenshot Update (Daily 2:00 AM JST)',
                replace_existing=True
            )

            if self._owns_scheduler:
                self.scheduler.start()

            print("[ECBRateCutsScreenshotScheduler] Started (Daily 2:00 AM JST)")

        except Exception as e:
            print(f"[ECBRateCutsScreenshotScheduler] Error starting: {e}")

    def stop(self):
        """Stop the ECB rate cuts screenshot scheduler"""
        try:
            if self._owns_scheduler and self.scheduler.running:
                self.scheduler.shutdown()
            print("[ECBRateCutsScreenshotScheduler] Stopped")
        except Exception as e:
            print(f"[ECBRateCutsScreenshotScheduler] Error stopping: {e}")


# Global scheduler instance
ecb_rate_cuts_screenshot_scheduler = ECBRateCutsScreenshotScheduler()
