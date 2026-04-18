"""
NYオプションカット 日次スケジューラー

investinglive.com のFXオプション期日記事を自動取得

スケジュール:
  - 毎営業日 15:30〜17:00 JST の間 15 分おきに記事チェック
    (15:30, 15:45, 16:00, 16:15, 16:30, 16:45, 17:00 の 7 回)
  ※ 記事が見つかったら以降のチェックはスキップ (_last_found_date)
"""
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")


class NyOptionCutScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._last_found_date = None

    def _import_service(self):
        try:
            from backend.services.market.ny_option_cut_service import ny_option_cut_service
        except ImportError:
            from services.market.ny_option_cut_service import ny_option_cut_service
        return ny_option_cut_service

    async def _check_article(self):
        """当日の記事が公開されているかチェック"""
        today = datetime.now(JST).date()

        # in-memory の早期スキップ
        if self._last_found_date == today:
            logger.info("[NYOptionCut] Already found today's article, skipping.")
            return

        try:
            service = self._import_service()

            # ファイルキャッシュに当日分があればネットワーク取得をスキップ
            # (コンテナ再起動で in-memory の _last_found_date が失われるケースに対応)
            cached = service._load_from_file()
            if cached and service._is_today(cached):
                self._last_found_date = today
                logger.info(
                    f"[NYOptionCut] Cache already has today's article ({today}), skipping."
                )
                return

            result = service.get_data(force_refresh=True)

            if result.get("status") == "published":
                self._last_found_date = today
                logger.info(f"[NYOptionCut] Article found for {today}")
            else:
                logger.info(f"[NYOptionCut] Article not yet published for {today}")
        except Exception as e:
            logger.error(f"[NYOptionCut] Check failed: {e}")

    def start(self):
        """スケジューラー開始"""
        # 15:30〜17:00 JST の間 15 分おき (記事公開が 15:30 を超えるケースに対応)
        schedule_times = [
            (15, 30), (15, 45),
            (16, 0), (16, 15), (16, 30), (16, 45),
            (17, 0),
        ]

        for hour, minute in schedule_times:
            self.scheduler.add_job(
                self._check_article,
                CronTrigger(
                    day_of_week="mon-fri",
                    hour=hour,
                    minute=minute,
                    timezone=JST,
                ),
                id=f"ny_option_cut_{hour:02d}{minute:02d}",
                replace_existing=True,
                misfire_grace_time=3600,
            )

        self.scheduler.start()
        logger.info(
            "[NYOptionCut] Scheduler started "
            "(15:30, 15:45, 16:00, 16:15, 16:30, 16:45, 17:00 JST)"
        )

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


ny_option_cut_scheduler = NyOptionCutScheduler()
