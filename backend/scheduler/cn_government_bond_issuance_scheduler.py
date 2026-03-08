"""
中国国債発行 日次スケジューラー

毎日 JST 18:00（CST 17:00）に MOF サイトから
新規の通知・公告をスクレイピングしてDBに格納。
"""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class CnGovernmentBondIssuanceScheduler:
    """国債発行 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    def _get_service(self):
        try:
            from backend.services.china.cn_government_bond_issuance_service import cn_government_bond_issuance_service
        except ImportError:
            from services.china.cn_government_bond_issuance_service import cn_government_bond_issuance_service
        return cn_government_bond_issuance_service

    async def _run(self):
        """新規分のみスクレイピングしてDB追加"""
        try:
            logger.info("[Scheduler] CnGovernmentBondIssuance: updating...")
            service = self._get_service()
            result = service.update_latest()
            meta = result.get("metadata", {})
            logger.info(
                f"[Scheduler] CnGovernmentBondIssuance: done. "
                f"notices={meta.get('total_notices')}, "
                f"results={meta.get('total_results')}, "
                f"upcoming={meta.get('upcoming_count')}"
            )
        except Exception as e:
            logger.error(f"[Scheduler] CnGovernmentBondIssuance error: {e}")

    def start(self):
        """スケジューラーを開始（毎日 JST 18:00）"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=18, minute=0, timezone=JST),
            id="cn_government_bond_issuance_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[Scheduler] CnGovernmentBondIssuance Scheduler started (daily 18:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


cn_government_bond_issuance_scheduler = CnGovernmentBondIssuanceScheduler()
