"""
日銀貸出動向スケジューラー

毎月1日から毎日9:30 JSTにチェック
更新できたらその月は以降スキップ
"""

import logging
from datetime import datetime
from typing import Dict, Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class BOJLendingScheduler:
    """日銀貸出動向スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._boj_lending_service = None

    def _get_boj_lending_service(self):
        """日銀貸出動向サービスを取得（遅延ロード）"""
        if self._boj_lending_service is None:
            try:
                from backend.services.japan.boj_lending_service import boj_lending_service
                self._boj_lending_service = boj_lending_service
            except ImportError:
                from services.japan.boj_lending_service import boj_lending_service
                self._boj_lending_service = boj_lending_service
        return self._boj_lending_service

    async def _update_boj_lending(self):
        """日銀貸出動向を更新"""
        try:
            logger.info("[Scheduler] Checking BOJ Lending Trends...")
            service = self._get_boj_lending_service()
            result = service.scheduled_update()
            logger.info(f"[Scheduler] BOJ Lending update result: {result}")
        except Exception as e:
            logger.error(f"[Scheduler] Error updating BOJ Lending: {e}")

    def start(self):
        """スケジューラーを開始"""
        try:
            # 日銀貸出動向: 毎日9:30 JSTにチェック
            self.scheduler.add_job(
                self._update_boj_lending,
                CronTrigger(hour=9, minute=30, timezone=JST),
                id="boj_lending",
                name="BOJ Lending Trends Update",
                replace_existing=True
            )

            self.scheduler.start()
            logger.info("[Scheduler] BOJ Lending Scheduler started")
            logger.info("[Scheduler] - BOJ Lending: Daily 09:30 JST (skip if already updated this month)")

        except Exception as e:
            logger.error(f"[Scheduler] Error starting BOJ Lending Scheduler: {e}")

    def shutdown(self):
        """スケジューラーを停止"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("[Scheduler] BOJ Lending Scheduler stopped")
        except Exception as e:
            logger.error(f"[Scheduler] Error stopping scheduler: {e}")

    def get_status(self) -> Dict[str, Any]:
        """スケジューラーのステータスを取得"""
        jobs = []
        if self.scheduler.running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
                })

        return {
            "running": self.scheduler.running,
            "jobs": jobs
        }

    def trigger_update(self) -> Dict[str, Any]:
        """日銀貸出動向の手動更新トリガー"""
        try:
            service = self._get_boj_lending_service()
            return service.scheduled_update()
        except Exception as e:
            logger.error(f"Error triggering BOJ Lending update: {e}")
            return {"status": "error", "reason": str(e)}


# シングルトンインスタンス
boj_lending_scheduler = BOJLendingScheduler()
