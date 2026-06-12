"""
PBOC 預金準備率 日次スケジューラー

毎日 JST 16:00 に武漢PBOCウェブサイトをスクレイピングして
DB未登録の新しい発表を取得・登録する。
"""
import asyncio
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class PbcRrrScheduler:
    """PBOC預金準備率 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._fetch_fn = None

    def _get_fetch_fn(self):
        if self._fetch_fn is None:
            try:
                from backend.services.china.ch_rrr_service import fetch_and_store_latest
                self._fetch_fn = fetch_and_store_latest
            except ImportError:
                from services.china.ch_rrr_service import fetch_and_store_latest
                self._fetch_fn = fetch_and_store_latest
        return self._fetch_fn

    async def _run(self):
        """預金準備率データを取得・更新"""
        try:
            logger.info("[Scheduler] PBC RRR: checking for new announcements...")
            fetch_fn = self._get_fetch_fn()
            # 同期スクレイピングのためワーカースレッドへ退避（イベントループ保護）
            count = await asyncio.to_thread(fetch_fn)
            if count > 0:
                # キャッシュをクリアして最新データを反映
                try:
                    from backend.services.china.ch_rrr_service import ch_rrr_service
                    ch_rrr_service.invalidate_cache()
                except ImportError:
                    from services.china.ch_rrr_service import ch_rrr_service
                    ch_rrr_service.invalidate_cache()
            logger.info(f"[Scheduler] PBC RRR: {count} new announcements added")
        except Exception as e:
            logger.error(f"[Scheduler] PBC RRR error: {e}")

    def start(self):
        """スケジューラーを開始（毎日 JST 16:00）"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=16, minute=0, timezone=JST),
            id="pbc_rrr_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[Scheduler] PBC RRR Scheduler started (daily 16:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


pbc_rrr_scheduler = PbcRrrScheduler()
