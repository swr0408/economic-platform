"""
日経225オプション 日次スケジューラー

JPX Settlement Price CSV: 毎営業日 ~16:45 JST (当日日付)
JPX Open Interest XLSX:   毎営業日 ~20:00 JST (前営業日日付)

スケジュール:
  - 毎営業日 17:00 JST: Settlement CSV取得 + ローカル保存
  - 毎営業日 20:30 JST: OI XLSX + Market Data取得・マージ + ローカル保存
  - 毎営業日 21:00 JST: リトライ
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")

LOCAL_DATA_DIR = Path(__file__).parent.parent / "data" / "nikkei_option_data"
LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

# JPX URLs
SETTLEMENT_CSV_URL = (
    "https://www.jpx.co.jp/markets/derivatives/settlement-price/"
    "tvdivq00000014l6-att/rb{date}.csv"
)
OPEN_INTEREST_URL = (
    "https://www.jpx.co.jp/markets/derivatives/trading-volume/"
    "tvdivq00000014nn-att/{date}open_interest.xlsx"
)
MARKET_DATA_URL = (
    "https://www.jpx.co.jp/markets/derivatives/trading-volume/"
    "tvdivq00000014nn-att/{date}_market_data_whole_day.xlsx"
)
OSE_TP_URL = (
    "https://www.jpx.co.jp/markets/derivatives/settlement-price/"
    "tvdivq00000014l6-att/ose{date}tp.csv"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _prev_business_day(d):
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


class Nikkei225OptionsScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    def _import_service(self):
        try:
            from backend.services.market.nikkei225_options_service import nikkei225_options_service
        except ImportError:
            from services.market.nikkei225_options_service import nikkei225_options_service
        return nikkei225_options_service

    def _download_and_save(self, url: str, local_path: Path) -> bool:
        """URLからダウンロードしてローカルに保存"""
        import requests

        if local_path.exists():
            return True

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 500:
                local_path.write_bytes(resp.content)
                logger.info(f"[NK225Options] Saved: {local_path.name} ({len(resp.content)} bytes)")
                return True
        except Exception as e:
            logger.debug(f"[NK225Options] Download failed {local_path.name}: {e}")
        return False

    async def _run_settlement(self):
        """Settlement CSV + ose*tp.csv 取得 → ローカル保存 → データ更新"""
        try:
            import requests

            today = datetime.now(JST).date()
            date_str = today.strftime("%Y%m%d")

            # Try today and recent business days
            for i in range(3):
                d = today - timedelta(days=i)
                if d.weekday() >= 5:
                    continue
                ds = d.strftime("%Y%m%d")

                # Download rb CSV
                rb_path = LOCAL_DATA_DIR / f"rb{ds}.csv"
                rb_url = SETTLEMENT_CSV_URL.format(date=ds)
                self._download_and_save(rb_url, rb_path)

                # Download ose*tp CSV
                ose_path = LOCAL_DATA_DIR / f"ose{ds}tp.csv"
                ose_url = OSE_TP_URL.format(date=ds)
                self._download_and_save(ose_url, ose_path)

                if rb_path.exists() or ose_path.exists():
                    break

            # Trigger data rebuild
            service = self._import_service()
            logger.info("[NK225Options] Fetching settlement data...")
            result = service.get_data(force_refresh=True)
            if result and result.get("data"):
                data = result["data"]
                date_val = data.get("date", "?")
                n_exp = len(data.get("expiries", []))
                logger.info(
                    f"[NK225Options] Settlement data updated: {date_val} "
                    f"({n_exp} expiries)"
                )
            else:
                logger.warning("[NK225Options] Settlement data fetch returned empty")
        except Exception as e:
            logger.error(f"[NK225Options] Error: {e}")
            import traceback
            traceback.print_exc()

    async def _run_oi_merge(self):
        """OI XLSX + Market Data 取得 → ローカル保存 → データ更新"""
        try:
            today = datetime.now(JST).date()

            # OI uses previous business day or current day
            for d in [today, _prev_business_day(today)]:
                ds = d.strftime("%Y%m%d")

                # Download OI XLSX
                oi_path = LOCAL_DATA_DIR / f"{ds}open_interest.xlsx"
                oi_url = OPEN_INTEREST_URL.format(date=ds)
                self._download_and_save(oi_url, oi_path)

                # Download Market Data XLSX
                md_path = LOCAL_DATA_DIR / f"{ds}_market_data_whole_day.xlsx"
                md_url = MARKET_DATA_URL.format(date=ds)
                self._download_and_save(md_url, md_path)

            # Trigger data rebuild
            service = self._import_service()
            logger.info("[NK225Options] Merging OI data...")
            result = service.get_data(force_refresh=True)
            if result and result.get("data"):
                logger.info("[NK225Options] OI merge completed")
            else:
                logger.warning("[NK225Options] OI merge returned empty")
        except Exception as e:
            logger.error(f"[NK225Options] OI merge error: {e}")

    def start(self):
        # 17:00 JST - Settlement CSV (published ~16:45)
        self.scheduler.add_job(
            self._run_settlement,
            CronTrigger(day_of_week="mon-fri", hour=17, minute=0, timezone=JST),
            id="nk225_options_settlement",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        # 20:30 JST - OI XLSX (published ~20:00)
        self.scheduler.add_job(
            self._run_oi_merge,
            CronTrigger(day_of_week="mon-fri", hour=20, minute=30, timezone=JST),
            id="nk225_options_oi",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        # 21:00 JST - Retry
        self.scheduler.add_job(
            self._run_settlement,
            CronTrigger(day_of_week="mon-fri", hour=21, minute=0, timezone=JST),
            id="nk225_options_retry",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[NK225Options] Scheduler started (17:00 + 20:30 + 21:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


nikkei225_options_scheduler = Nikkei225OptionsScheduler()
