"""
Entitlement 期限切れスイープ 日次スケジューラー

収益化計画 4章「β終了後は原則 Free に戻す」/ Table 11「手動決済期間は
current_period_end を必ず管理する」の自動実行部分。

スケジュール:
  - 毎日 09:00 JST: 期限切れ entitlement を expired にし、ユーザーを
    general へ降格 + トークン失効 (master の role は決して変更しない)
  - 起動時 (+2分): 再起動跨ぎでジョブを逃しても必ず1回は実行する

DB I/O のみの軽量ジョブだが、既知のイベントループブロック対策として
asyncio.to_thread でワーカースレッドに退避する。
"""
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")


class EntitlementScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    def _sweep_sync(self):
        try:
            from backend.core.billing.entitlement_service import sweep_expired_entitlements
        except ImportError:
            from core.billing.entitlement_service import sweep_expired_entitlements
        result = sweep_expired_entitlements()
        if result.get("expired_entitlements"):
            logger.info(f"[EntitlementScheduler] sweep result: {result}")

    async def _sweep(self):
        try:
            # 同期 DB I/O をワーカースレッドへ退避 (イベントループ保護)
            await asyncio.to_thread(self._sweep_sync)
        except Exception as e:
            logger.error(f"[EntitlementScheduler] sweep failed: {e}")

    def start(self):
        self.scheduler.add_job(
            self._sweep,
            CronTrigger(hour=9, minute=0, timezone=JST),
            id="entitlement_expiry_sweep",
            replace_existing=True,
            misfire_grace_time=6 * 3600,
        )
        # 起動時スイープ (再起動跨ぎの取りこぼし防止)
        self.scheduler.add_job(
            self._sweep,
            DateTrigger(run_date=datetime.now(JST) + timedelta(minutes=2)),
            id="entitlement_sweep_startup",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[EntitlementScheduler] Started (daily 09:00 JST + startup sweep)")

    def shutdown(self):
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
        except Exception:
            pass


entitlement_scheduler = EntitlementScheduler()
