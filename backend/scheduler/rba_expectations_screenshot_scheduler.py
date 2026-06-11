"""
RBA MacroMicro スクリーンショット日次スケジューラー

MacroMicro のチャートスクリーンショット (Expectations + OIS) を
毎日 JST 6:00 に自動更新する。
フォールバックとして JST 12:00 にも実行（朝の取得が失敗した場合に備える）。
"""
import logging
from zoneinfo import ZoneInfo

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class RbaExpectationsScreenshotScheduler:
    """RBA Expectations + OIS スクリーンショット日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._expectations_service = None
        self._ois_service = None

    def _get_expectations_service(self):
        if self._expectations_service is None:
            try:
                from backend.services.australia.rba_expectations_screenshot_service import (
                    rba_expectations_screenshot_service,
                )
            except ImportError:
                from services.australia.rba_expectations_screenshot_service import (
                    rba_expectations_screenshot_service,
                )
            self._expectations_service = rba_expectations_screenshot_service
        return self._expectations_service

    def _get_ois_service(self):
        if self._ois_service is None:
            try:
                from backend.services.australia.rba_ois_screenshot_service import (
                    rba_ois_screenshot_service,
                )
            except ImportError:
                from services.australia.rba_ois_screenshot_service import (
                    rba_ois_screenshot_service,
                )
            self._ois_service = rba_ois_screenshot_service
        return self._ois_service

    async def _run(self):
        # Playwright sync API はブロッキング。ワーカースレッドへ退避。
        # 直接実行するとイベントループを占有し login 等が応答不能になる。
        await asyncio.to_thread(self._run_sync)

    def _run_sync(self):
        """スクリーンショットを強制更新（Expectations + OIS）"""
        # --- RBA Expectations ---
        try:
            logger.info("[Scheduler] RBA Expectations Screenshot: capturing...")
            service = self._get_expectations_service()
            result = service.capture_all_screenshots(force_refresh=True)
            year_end_ok = result.get("year_end_rate", {}).get("success", False)
            rate_cuts_ok = result.get("rate_cuts", {}).get("success", False)
            logger.info(
                f"[Scheduler] RBA Expectations Screenshot: done — "
                f"year_end_rate={year_end_ok}, rate_cuts={rate_cuts_ok}"
            )
        except Exception as e:
            logger.error(
                f"[Scheduler] RBA Expectations Screenshot error: {e}",
                exc_info=True,
            )

        # --- RBA OIS ---
        try:
            logger.info("[Scheduler] RBA OIS Screenshot: capturing...")
            ois_service = self._get_ois_service()
            ois_result = ois_service.capture_all_screenshots(force_refresh=True)
            ois_1m_ok = ois_result.get("ois_1m", {}).get("success", False)
            ois_3m_ok = ois_result.get("ois_3m", {}).get("success", False)
            ois_6m_ok = ois_result.get("ois_6m", {}).get("success", False)
            logger.info(
                f"[Scheduler] RBA OIS Screenshot: done — "
                f"ois_1m={ois_1m_ok}, ois_3m={ois_3m_ok}, ois_6m={ois_6m_ok}"
            )
        except Exception as e:
            logger.error(
                f"[Scheduler] RBA OIS Screenshot error: {e}",
                exc_info=True,
            )

    def start(self):
        """スケジューラーを開始（毎日 JST 6:00, 12:00）"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=6, minute=0, timezone=JST),
            id="rba_screenshots_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=12, minute=0, timezone=JST),
            id="rba_screenshots_fallback",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info(
            "[Scheduler] RBA Screenshots Scheduler started "
            "(Expectations + OIS, daily JST 6:00, 12:00)"
        )

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


rba_expectations_screenshot_scheduler = RbaExpectationsScreenshotScheduler()
