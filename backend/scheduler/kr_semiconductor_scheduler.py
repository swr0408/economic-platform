"""
韓国半導体輸出 日次更新スケジューラー

産業通商部 (motir.go.kr) の ICT 수출입 동향 レポートから
半導体輸出の新しい月次値を kr_semiconductor_history.json に取り込む。

- 起動時 catch-up (30秒後に1回): バックエンド停止期間の取りこぼしを回復
- 毎日 13:30 JST: ICT確報は対象月翌月の12〜15日頃 11:00 KST に公表されるため、
  公表日の午後に確実に拾える時刻に設定
- updater側に安価な鮮度ガードあり (期待される最新月が履歴に揃っていれば
  ネットワークアクセスせず即skip) → 日次実行してもコストはほぼゼロ
- blocking HTTP は asyncio.to_thread でイベントループ外に逃がす
  (ループ上で requests を呼ぶと全エンドポイントが固まる既知の致命バグ)
"""
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


def _update_sync() -> dict:
    """履歴JSONの更新 (同期・blocking HTTPあり)"""
    # "global" は予約語のため importlib 経由でimport
    import importlib
    updater = importlib.import_module("services.global.kr_semiconductor_updater")
    return updater.update_history()


class KrSemiconductorScheduler:
    """韓国半導体輸出 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._is_running = False

    async def _run(self):
        try:
            result = await asyncio.to_thread(_update_sync)
            status = result.get("status")
            if status == "updated":
                logger.info(f"[KrSemiScheduler] History updated: {result}")
            elif status == "error":
                logger.error(f"[KrSemiScheduler] Update error: {result}")
            else:
                logger.info(f"[KrSemiScheduler] {status}: {result}")
        except Exception as e:
            logger.error(f"[KrSemiScheduler] Run failed: {e}", exc_info=True)

    def start(self):
        if self._is_running:
            logger.warning("[KrSemiScheduler] Already running")
            return

        # 起動時 catch-up (30秒後に1回)
        self.scheduler.add_job(
            self._run,
            "date",
            run_date=datetime.now(JST) + timedelta(seconds=30),
            id="kr_semiconductor_catchup_startup",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        # 毎日 13:30 JST
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=13, minute=30, timezone=JST),
            id="kr_semiconductor_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        self._is_running = True
        logger.info("[KrSemiScheduler] Started (startup catch-up + daily 13:30 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
            self._is_running = False
        except Exception:
            pass


kr_semiconductor_scheduler = KrSemiconductorScheduler()
