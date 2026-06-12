"""
China SHIBOR 日次スケジューラー

毎日 JST 15:30（CST 14:30）に shibor.org API から
当年データを取得して Excel 上書き → キャッシュ再構築。
"""
import asyncio
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class CnShiborScheduler:
    """SHIBOR 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    def _get_service(self):
        try:
            from backend.services.china.cn_shibor_service import cn_shibor_service
        except ImportError:
            from services.china.cn_shibor_service import cn_shibor_service
        return cn_shibor_service

    async def _run(self):
        """当年 Excel を更新してキャッシュ再構築"""
        try:
            logger.info("[Scheduler] CnShibor: updating current year...")
            service = self._get_service()
            # 同期 requests（+ time.sleep）のためワーカースレッドへ退避（イベントループ保護）
            result = await asyncio.to_thread(service.update_current_year)
            total = result.get("metadata", {}).get("total_records", 0)
            latest_date = (result.get("latest") or {}).get("date")
            logger.info(
                f"[Scheduler] CnShibor: done. "
                f"total={total}, latest={latest_date}"
            )
        except Exception as e:
            logger.error(f"[Scheduler] CnShibor error: {e}")

    def start(self):
        """スケジューラーを開始（毎日 JST 15:30）"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=15, minute=30, timezone=JST),
            id="cn_shibor_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[Scheduler] CnShibor Scheduler started (daily 15:30 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


cn_shibor_scheduler = CnShiborScheduler()
