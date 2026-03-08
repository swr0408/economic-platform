"""
China Central Parity Rate 日次スケジューラー

毎日 JST 17:00（CST 16:00）に chinamoney.com.cn API から
当年データを取得して Excel 上書き → キャッシュ再構築。

Fixingは毎日 9:15 CST (10:15 JST) に発表されるが、
APIへの反映は午後になるため 16:00 CST に実行する。
"""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class CnCentralParityScheduler:
    """Central Parity Rate 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    def _get_service(self):
        try:
            from backend.services.china.cn_central_parity_service import cn_central_parity_service
        except ImportError:
            from services.china.cn_central_parity_service import cn_central_parity_service
        return cn_central_parity_service

    async def _run(self):
        """当年 Excel を更新してキャッシュ再構築"""
        try:
            logger.info("[Scheduler] CnCentralParity: updating current year...")
            service = self._get_service()
            result = service.update_current_year()
            total = result.get("metadata", {}).get("total_records", 0)
            latest = result.get("latest") or {}
            logger.info(
                f"[Scheduler] CnCentralParity: done. "
                f"total={total}, latest_fixing={latest.get('fixing_date')}, "
                f"fixing={latest.get('fixing')}"
            )
        except Exception as e:
            logger.error(f"[Scheduler] CnCentralParity error: {e}")

    def start(self):
        """スケジューラーを開始（毎日 JST 17:00）"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=17, minute=0, timezone=JST),
            id="cn_central_parity_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[Scheduler] CnCentralParity Scheduler started (daily 17:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


cn_central_parity_scheduler = CnCentralParityScheduler()
