"""
百度迁徙（Baidu Migration）Screenshot Scheduler
毎日 JST 18:00（CTC 17:00）にスクリーンショットを自動更新
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


JST = ZoneInfo("Asia/Tokyo")


class CnBaiduMigrationScheduler:
    """Scheduler for Baidu Migration screenshot updates"""

    def __init__(self, shared_scheduler: AsyncIOScheduler = None):
        self.scheduler = shared_scheduler
        self._owns_scheduler = shared_scheduler is None

        if self._owns_scheduler:
            self.scheduler = AsyncIOScheduler(timezone=JST)

    async def update_screenshot(self):
        """
        Update Baidu Migration screenshot
        Runs daily at 18:00 JST (17:00 CTC)
        """
        try:
            from services.china.cn_baidu_migration_screenshot_service import cn_baidu_migration_screenshot_service

            print(f"[BaiduMigrationScheduler] Starting screenshot update at {datetime.now(JST).isoformat()}")

            # sync Playwright をイベントループ上で直接起動すると毎回例外で即死するため
            # ワーカースレッドへ退避する
            result = await asyncio.to_thread(
                cn_baidu_migration_screenshot_service.capture_screenshot,
                force_refresh=True,
            )

            if result["success"]:
                print("[BaiduMigrationScheduler] Successfully updated screenshot")
            else:
                print("[BaiduMigrationScheduler] Failed to update screenshot")

        except Exception as e:
            print(f"[BaiduMigrationScheduler] Error updating screenshot: {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """Start the Baidu Migration screenshot scheduler"""
        try:
            # 毎日 JST 18:00（CTC 17:00）に実行
            self.scheduler.add_job(
                self.update_screenshot,
                CronTrigger(hour=18, minute=0, timezone=JST),
                id='cn_baidu_migration_screenshot_update',
                name='Baidu Migration Screenshot Update (Daily 18:00 JST / 17:00 CTC)',
                replace_existing=True
            )

            if self._owns_scheduler:
                self.scheduler.start()

            print("[BaiduMigrationScheduler] Started (Daily 18:00 JST / 17:00 CTC)")

        except Exception as e:
            print(f"[BaiduMigrationScheduler] Error starting: {e}")

    def stop(self):
        """Stop the Baidu Migration screenshot scheduler"""
        try:
            if self._owns_scheduler and self.scheduler.running:
                self.scheduler.shutdown()
            print("[BaiduMigrationScheduler] Stopped")
        except Exception as e:
            print(f"[BaiduMigrationScheduler] Error stopping: {e}")


# Global scheduler instance
cn_baidu_migration_scheduler = CnBaiduMigrationScheduler()
