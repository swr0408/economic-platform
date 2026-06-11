"""
COMEX倉庫在庫 日次スケジューラー

CME Delivery Reports から Gold/Silver/Copper の在庫データを取得し
DBにUPSERT後、Redisキャッシュをクリアする。

スケジュール:
  - 毎日 JST 07:00（CME前日分レポート取得）
  - 毎日 JST 12:00（リトライ）
"""
import logging
from zoneinfo import ZoneInfo

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


def _refresh_gold():
    """Gold在庫をforce_refresh"""
    try:
        from services.market.comex_gold_stock_service import comex_gold_stock_service
    except ImportError:
        from backend.services.market.comex_gold_stock_service import comex_gold_stock_service

    result = comex_gold_stock_service.get_data(force_refresh=True)
    data = result.get("data", [])
    latest = result.get("latest", {})
    logger.info(
        f"[ComexScheduler] Gold: {len(data)} points, "
        f"latest={latest.get('date', 'N/A')}"
    )


def _refresh_silver():
    """Silver在庫をforce_refresh"""
    try:
        from services.market.comex_silver_stock_service import comex_silver_stock_service
    except ImportError:
        from backend.services.market.comex_silver_stock_service import comex_silver_stock_service

    result = comex_silver_stock_service.get_data(force_refresh=True)
    data = result.get("data", [])
    latest = result.get("latest", {})
    logger.info(
        f"[ComexScheduler] Silver: {len(data)} points, "
        f"latest={latest.get('date', 'N/A')}"
    )


def _refresh_copper():
    """Copper在庫をforce_refresh"""
    try:
        from services.market.comex_copper_stock_service import comex_copper_stock_service
    except ImportError:
        from backend.services.market.comex_copper_stock_service import comex_copper_stock_service

    result = comex_copper_stock_service.get_data(force_refresh=True)
    data = result.get("data", [])
    latest = result.get("latest", {})
    logger.info(
        f"[ComexScheduler] Copper: {len(data)} points, "
        f"latest={latest.get('date', 'N/A')}"
    )


class ComexStockScheduler:
    """COMEX倉庫在庫 日次スケジューラー（Gold/Silver/Copper）"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    async def _run(self):
        # ブロッキング I/O (requests/yfinance/sync DB) をワーカースレッドへ退避。
        # 直接実行するとイベントループを占有し login 等が応答不能になる。
        await asyncio.to_thread(self._run_sync)

    def _run_sync(self):
        """全3メタルの在庫データを更新"""
        logger.info("[ComexScheduler] Starting daily COMEX stock update...")
        for name, fn in [("Gold", _refresh_gold), ("Silver", _refresh_silver), ("Copper", _refresh_copper)]:
            try:
                fn()
            except Exception as e:
                logger.error(f"[ComexScheduler] {name} error: {e}")
        logger.info("[ComexScheduler] Daily update complete")

    def start(self):
        """スケジューラーを開始
        - 毎日 07:00 JST
        - 毎日 12:00 JST（リトライ）
        """
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=7, minute=0, timezone=JST),
            id="comex_stock_daily_07",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=12, minute=0, timezone=JST),
            id="comex_stock_daily_12",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[ComexScheduler] Started (07:00 + 12:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


comex_stock_scheduler = ComexStockScheduler()
