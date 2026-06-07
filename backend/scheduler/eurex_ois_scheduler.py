"""
Eurex Three-Month Euro STR Futures OIS 日次スケジューラー

Eurex D.Settle は CET 20:00-20:10 (夏時間) / 21:00-21:10 (冬時間) に更新される。
JST では同じ時刻 (夏: 03:00 翌日 / 冬: 05:00 翌日 — ただしサービス側では
JST 20:00-21:10 と解釈されている)。

安全策として JST 4:30 と 5:30 の2回取得を試みる。
追加で平日 JST 7:00 にフォールバック取得を行い、
前2回が失敗していた場合でも当日データを確保する。
"""
import asyncio
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
        """Eurex OIS データを強制取得。

        サービスは Playwright sync_api を内部利用するため asyncio ループ上で
        直接呼ぶと "Sync API inside asyncio loop" エラーになる。別スレッドで
        実行することで sync_api が独自のループを張れるようにする。
        """
        try:
            logger.info("[Scheduler] Eurex OIS: fetching latest data...")
            service = self._get_service()
            result = await asyncio.to_thread(service.get_eurex_ois_data, True)
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
        """スケジューラーを開始（平日 JST 4:30, 5:30, 7:00）。

        `misfire_grace_time=None` で時間制限を撤廃。これにより `--reload` などで
        コンテナが終日再起動を繰り返しても、その日の cron 時刻を過ぎた直後の
        起動で即座にキャッチアップ実行される。さらに、起動直後にキャッシュが
        古ければワンショットで取得を試みる。
        """
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=4, minute=30, day_of_week="mon-fri", timezone=JST),
            id="eurex_ois_daily_1",
            replace_existing=True,
            misfire_grace_time=None,
            coalesce=True,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=5, minute=30, day_of_week="mon-fri", timezone=JST),
            id="eurex_ois_daily_2",
            replace_existing=True,
            misfire_grace_time=None,
            coalesce=True,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=7, minute=0, day_of_week="mon-fri", timezone=JST),
            id="eurex_ois_daily_fallback",
            replace_existing=True,
            misfire_grace_time=None,
            coalesce=True,
        )
        # 起動時の即時キャッチアップ: キャッシュが古ければ取得を試みる
        self._schedule_startup_catchup()
        self.scheduler.start()
        logger.info(
            "[Scheduler] Eurex OIS Scheduler started "
            "(weekdays JST 4:30, 5:30, 7:00, misfire grace=unlimited)"
        )

    def _schedule_startup_catchup(self):
        """起動直後にキャッシュ鮮度を確認し、古ければ取得をキューに入れる。"""
        from datetime import datetime, timedelta
        try:
            service = self._get_service()
            cache = getattr(service, "get_cache_status", lambda: {})()
            last_updated_str = cache.get("last_updated") if isinstance(cache, dict) else None
            now_jst = datetime.now(JST)
            stale = True
            if last_updated_str:
                try:
                    last = datetime.fromisoformat(last_updated_str)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=JST)
                    age = now_jst - last
                    # 平日かつキャッシュが今日朝のcron時刻(4:30 JST)より古い場合のみ取得
                    today_release_cutoff = now_jst.replace(hour=4, minute=30, second=0, microsecond=0)
                    stale = (now_jst >= today_release_cutoff and last < today_release_cutoff) or age >= timedelta(days=1)
                except Exception:
                    stale = True

            if stale:
                # 1分後にワンショット実行(起動直後の混雑を避ける)
                run_at = now_jst + timedelta(minutes=1)
                self.scheduler.add_job(
                    self._run,
                    "date",
                    run_date=run_at,
                    id="eurex_ois_startup_catchup",
                    replace_existing=True,
                    misfire_grace_time=None,
                )
                logger.info(f"[Scheduler] Eurex OIS: startup catch-up queued at {run_at.isoformat()}")
        except Exception as e:
            logger.warning(f"[Scheduler] Eurex OIS startup catch-up failed to schedule: {e}")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


eurex_ois_scheduler = EurexOISScheduler()
