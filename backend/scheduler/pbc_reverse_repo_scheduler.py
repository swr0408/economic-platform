"""
PBOC 逆回購金利 日次スケジューラー

毎日 JST 16:00 に PBOCウェブサイトをスクレイピングして
DB未登録の新しいデータを取得・登録する。

PBOCは北京時間（CST = JST-1）の午前中に公告を出す。
JST 16:00 = CST 15:00 に実行することで当日データを確実に取得。
"""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class PbcReverseRepoScheduler:
    """PBOC逆回購金利 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service = None

    def _get_service(self):
        if self._service is None:
            try:
                from backend.services.china.ch_reverse_repo_rate_service import fetch_and_store_latest
                self._service = fetch_and_store_latest
            except ImportError:
                from services.china.ch_reverse_repo_rate_service import fetch_and_store_latest
                self._service = fetch_and_store_latest
        return self._service

    async def _run(self):
        """逆回購金利データを取得・更新"""
        try:
            logger.info("[Scheduler] PBC Reverse Repo: checking for new data...")
            fetch_fn = self._get_service()
            count = fetch_fn()
            logger.info(f"[Scheduler] PBC Reverse Repo: {count} new records added")
        except Exception as e:
            logger.error(f"[Scheduler] PBC Reverse Repo error: {e}")

    def start(self):
        """スケジューラーを開始（毎日 JST 16:00）"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=16, minute=0, timezone=JST),
            id="pbc_reverse_repo_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[Scheduler] PBC Reverse Repo Scheduler started (daily 16:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


pbc_reverse_repo_scheduler = PbcReverseRepoScheduler()
