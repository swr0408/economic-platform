"""
日本潜在成長率スケジューラー

2つの潜在成長率指標を定期的にチェック・更新する:

1. 内閣府潜在成長率
   - 更新: 不定期（月例経済報告の付属資料として公表）
   - スケジュール: 毎日9:00 JSTにチェック
   - 更新した月は以降スキップ

2. 日銀潜在成長率
   - 更新: 四半期毎（1月、4月、7月、10月の7日頃）
   - スケジュール: 該当月は毎日9:00 JSTにチェック
   - 更新したらその月は以降スキップ
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class JapanPotentialGrowthScheduler:
    """日本潜在成長率スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._potential_growth_service = None
        self._boj_potential_growth_service = None

    def _get_potential_growth_service(self):
        """内閣府潜在成長率サービスを取得（遅延ロード）"""
        if self._potential_growth_service is None:
            try:
                from backend.services.japan.potential_growth_service import potential_growth_service
                self._potential_growth_service = potential_growth_service
            except ImportError:
                from services.japan.potential_growth_service import potential_growth_service
                self._potential_growth_service = potential_growth_service
        return self._potential_growth_service

    def _get_boj_potential_growth_service(self):
        """日銀潜在成長率サービスを取得（遅延ロード）"""
        if self._boj_potential_growth_service is None:
            try:
                from backend.services.japan.boj_potential_growth_service import boj_potential_growth_service
                self._boj_potential_growth_service = boj_potential_growth_service
            except ImportError:
                from services.japan.boj_potential_growth_service import boj_potential_growth_service
                self._boj_potential_growth_service = boj_potential_growth_service
        return self._boj_potential_growth_service

    async def _update_cabinet_office_potential_growth(self):
        """内閣府潜在成長率を更新"""
        try:
            logger.info("[Scheduler] Checking Cabinet Office Potential Growth Rate...")
            service = self._get_potential_growth_service()
            # 同期 requests/Excel 解析のためワーカースレッドへ退避（イベントループ保護）
            result = await asyncio.to_thread(service.scheduled_update)
            logger.info(f"[Scheduler] Cabinet Office Potential Growth update result: {result}")
        except Exception as e:
            logger.error(f"[Scheduler] Error updating Cabinet Office Potential Growth: {e}")

    async def _update_boj_potential_growth(self):
        """日銀潜在成長率を更新"""
        try:
            logger.info("[Scheduler] Checking BOJ Potential Growth Rate...")
            service = self._get_boj_potential_growth_service()
            # 同期 requests/Excel 解析のためワーカースレッドへ退避（イベントループ保護）
            result = await asyncio.to_thread(service.scheduled_update)
            logger.info(f"[Scheduler] BOJ Potential Growth update result: {result}")
        except Exception as e:
            logger.error(f"[Scheduler] Error updating BOJ Potential Growth: {e}")

    def start(self):
        """スケジューラーを開始"""
        try:
            # 内閣府潜在成長率: 毎日9:00 JSTにチェック
            self.scheduler.add_job(
                self._update_cabinet_office_potential_growth,
                CronTrigger(hour=9, minute=0, timezone=JST),
                id="cabinet_office_potential_growth",
                name="Cabinet Office Potential Growth Rate Update",
                replace_existing=True
            )

            # 日銀潜在成長率: 毎日9:00 JSTにチェック（サービス側で対象月かどうかを判定）
            self.scheduler.add_job(
                self._update_boj_potential_growth,
                CronTrigger(hour=9, minute=0, timezone=JST),
                id="boj_potential_growth",
                name="BOJ Potential Growth Rate Update",
                replace_existing=True
            )

            self.scheduler.start()
            logger.info("[Scheduler] Japan Potential Growth Scheduler started")
            logger.info("[Scheduler] - Cabinet Office: Daily 09:00 JST (skip if already updated this month)")
            logger.info("[Scheduler] - BOJ: Daily 09:00 JST in Jan/Apr/Jul/Oct (skip if already updated)")

        except Exception as e:
            logger.error(f"[Scheduler] Error starting Japan Potential Growth Scheduler: {e}")

    def shutdown(self):
        """スケジューラーを停止"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("[Scheduler] Japan Potential Growth Scheduler stopped")
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

    def trigger_cabinet_office_update(self) -> Dict[str, Any]:
        """内閣府潜在成長率の手動更新トリガー"""
        try:
            service = self._get_potential_growth_service()
            return service.scheduled_update()
        except Exception as e:
            logger.error(f"Error triggering Cabinet Office update: {e}")
            return {"status": "error", "reason": str(e)}

    def trigger_boj_update(self) -> Dict[str, Any]:
        """日銀潜在成長率の手動更新トリガー"""
        try:
            service = self._get_boj_potential_growth_service()
            return service.scheduled_update()
        except Exception as e:
            logger.error(f"Error triggering BOJ update: {e}")
            return {"status": "error", "reason": str(e)}


# シングルトンインスタンス
japan_potential_growth_scheduler = JapanPotentialGrowthScheduler()
