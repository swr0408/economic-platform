"""
Eurex Three-Month Euro STR Futures OIS 日次スケジューラー

Eurex D.Settle は CET 20:00-20:10 (夏時間) / 21:00-21:10 (冬時間) に更新される。
JST では同じ時刻 (夏: 03:00 翌日 / 冬: 05:00 翌日 — ただしサービス側では
JST 20:00-21:10 と解釈されている)。

安全策として JST 4:30 と 5:30 の2回取得を試みる。
追加で平日 JST 7:00 にフォールバック取得を行い、
前2回が失敗していた場合でも当日データを確保する。
"""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class EurexOISScheduler:
    """Eurex OIS 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service = None

    def _get_service(self):
        if self._service is None:
            try:
                from backend.services.eurozone.eurex_ois_service import eurex_ois_service
                self._service = eurex_ois_service
            except ImportError:
                from services.eurozone.eurex_ois_service import eurex_ois_service
                self._service = eurex_ois_service
        return self._service

    async def _run(self):
        """Eurex OIS データを強制取得"""
        try:
            logger.info("[Scheduler] Eurex OIS: fetching latest data...")
            service = self._get_service()
            result = service.get_eurex_ois_data(force_refresh=True)
            source = result.get("source", "unknown")
            current = result.get("current", {})
            count = len(current.get("data", []))
            logger.info(
                f"[Scheduler] Eurex OIS: done — source={source}, "
                f"date={current.get('date')}, contracts={count}"
            )
        except Exception as e:
            logger.error(f"[Scheduler] Eurex OIS error: {e}", exc_info=True)

    def start(self):
        """スケジューラーを開始（平日 JST 4:30, 5:30, 7:00）"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=4, minute=30, day_of_week="mon-fri", timezone=JST),
            id="eurex_ois_daily_1",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=5, minute=30, day_of_week="mon-fri", timezone=JST),
            id="eurex_ois_daily_2",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=7, minute=0, day_of_week="mon-fri", timezone=JST),
            id="eurex_ois_daily_fallback",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info(
            "[Scheduler] Eurex OIS Scheduler started "
            "(weekdays JST 4:30, 5:30, 7:00)"
        )

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


eurex_ois_scheduler = EurexOISScheduler()
