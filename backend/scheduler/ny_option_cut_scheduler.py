"""
NYオプションカット 日次スケジューラー

investinglive.com のFXオプション期日記事を自動取得

スケジュール:
  - 毎営業日 15:30〜17:00 JST の間 15 分おきに記事チェック
    (15:30, 15:45, 16:00, 16:15, 16:30, 16:45, 17:00 の 7 回)
  - 公開遅延フォールバック: 18:00, 20:00 JST
  ※ 記事が見つかったら以降のチェックはスキップ (_last_found_date)

取りこぼし対策:
  - 起動時キャッチアップ: キャッシュが直近営業日より古ければ
    service.fetch_latest_available() で過去営業日まで遡って復旧
    (investinglive は過去日付の記事も残るため遡及可能)
  - すべてのフェッチは asyncio.to_thread でワーカースレッドに退避
    (同期 requests + Playwright をイベントループ上で直接呼ぶと
     全エンドポイントが応答不能になる既知バグの再発防止)
"""
import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
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

    def _check_article_sync(self):
        """当日の記事が公開されているかチェック（同期・ワーカースレッドで実行）"""
        today = datetime.now(JST).date()

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

    async def _check_article(self):
        """当日の記事チェック（async ラッパー）"""
        today = datetime.now(JST).date()

        # in-memory の早期スキップ
        if self._last_found_date == today:
            logger.info("[NYOptionCut] Already found today's article, skipping.")
            return

        try:
            # 同期 requests + Playwright をイベントループから隔離
            await asyncio.to_thread(self._check_article_sync)
        except Exception as e:
            logger.error(f"[NYOptionCut] Check failed: {e}")

    def _catch_up_sync(self):
        """起動時キャッチアップ（同期・ワーカースレッドで実行）

        キャッシュが直近営業日より古い場合、過去営業日まで遡って
        直近の公開済み記事を取得する。
        """
        service = self._import_service()
        result = service.fetch_latest_available(max_back_days=7)
        data = result.get("data") or {}
        logger.info(
            f"[NYOptionCut] Startup catch-up done: "
            f"status={result.get('status')}, article_date={data.get('date')}"
        )
        if service._is_today(result):
            self._last_found_date = datetime.now(JST).date()

    async def _catch_up(self):
        try:
            await asyncio.to_thread(self._catch_up_sync)
        except Exception as e:
            logger.error(f"[NYOptionCut] Startup catch-up failed: {e}")

    def start(self):
        """スケジューラー開始"""
        # 15:30〜17:00 JST の間 15 分おき (記事公開が 15:30 を超えるケースに対応)
        # + 公開が大幅に遅れた日のためのフォールバック (18:00, 20:00)
        schedule_times = [
            (15, 30), (15, 45),
            (16, 0), (16, 15), (16, 30), (16, 45),
            (17, 0),
            (18, 0), (20, 0),
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

        # 起動時キャッチアップ (スケジューラ停止期間の取りこぼし復旧)
        self.scheduler.add_job(
            self._catch_up,
            DateTrigger(run_date=datetime.now(JST) + timedelta(seconds=30)),
            id="ny_option_cut_startup_catchup",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        self.scheduler.start()
        logger.info(
            "[NYOptionCut] Scheduler started "
            "(15:30-17:00 every 15min, fallback 18:00/20:00 JST, startup catch-up)"
        )

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


ny_option_cut_scheduler = NyOptionCutScheduler()
