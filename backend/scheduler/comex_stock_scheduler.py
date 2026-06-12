"""
COMEX倉庫在庫 日次スケジューラー

CME Delivery Reports から Gold/Silver/Copper の在庫データを取得し
DBにUPSERT後、Redisキャッシュをクリアする。

スケジュール:
  - 毎日 JST 07:00（CME前日分レポート取得）
  - 毎日 JST 12:00（リトライ）
  - 起動時キャッチアップ: 当日まだ成功していなければ即時実行

※ CME の Gold/Silver/Copper_Stocks.xls は「当日分のみのスナップショット」で
  過去日は遡及取得できない。07:00/12:00 の両方を逃すとその日のデータは
  永久欠損するため、起動時キャッチアップが必須 (nikkei225 options と同型)。
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# 当日成功マーカー (uvicorn --reload 等の頻繁な再起動で CME を叩き直さないため)
_RUN_MARKER = Path(__file__).resolve().parents[1] / "data" / "cache" / "market" / "_comex_stock_last_run.txt"


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
        ok = 0
        for name, fn in [("Gold", _refresh_gold), ("Silver", _refresh_silver), ("Copper", _refresh_copper)]:
            try:
                fn()
                ok += 1
            except Exception as e:
                logger.error(f"[ComexScheduler] {name} error: {e}")
        logger.info(f"[ComexScheduler] Daily update complete ({ok}/3 ok)")
        # 全滅時はマーカーを書かない (起動時キャッチアップで再試行させる)
        if ok > 0:
            try:
                _RUN_MARKER.write_text(datetime.now(JST).strftime("%Y-%m-%d"), encoding="utf-8")
            except Exception as e:
                logger.warning(f"[ComexScheduler] run marker write failed: {e}")

    async def _startup_catchup(self):
        """起動時キャッチアップ: 当日まだ成功していなければ即時取得

        CME のレポートは当日分しか取得できないため、07:00/12:00 のジョブを
        両方逃した日 (停止・ループ詰まり) でも、その日のうちに再起動すれば
        ここで回収できる。
        """
        try:
            today = datetime.now(JST).strftime("%Y-%m-%d")
            if _RUN_MARKER.exists() and _RUN_MARKER.read_text(encoding="utf-8").strip() == today:
                logger.info("[ComexScheduler] Startup catch-up: already ran today, skipping")
                return
            logger.info("[ComexScheduler] Startup catch-up: fetching today's snapshot...")
            await asyncio.to_thread(self._run_sync)
        except Exception as e:
            logger.error(f"[ComexScheduler] Startup catch-up error: {e}")

    def start(self):
        """スケジューラーを開始
        - 毎日 07:00 JST
        - 毎日 12:00 JST（リトライ）
        - 起動時キャッチアップ（当日未取得なら即時）
        """
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=7, minute=0, timezone=JST),
            id="comex_stock_daily_07",
            replace_existing=True,
            # 当日中ならいつ実行しても価値があるスナップショットなので猶予を長めに
            misfire_grace_time=6 * 3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=12, minute=0, timezone=JST),
            id="comex_stock_daily_12",
            replace_existing=True,
            misfire_grace_time=6 * 3600,
        )
        self.scheduler.add_job(
            self._startup_catchup,
            DateTrigger(run_date=datetime.now(JST) + timedelta(seconds=60)),
            id="comex_stock_startup_catchup",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[ComexScheduler] Started (07:00 + 12:00 JST + startup catch-up)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


comex_stock_scheduler = ComexStockScheduler()
