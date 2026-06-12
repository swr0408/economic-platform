"""
日経225オプション 日次スケジューラー

JPX Settlement Price CSV: 毎営業日 ~16:45 JST (当日日付)
JPX Open Interest XLSX:   毎営業日 ~20:00 JST (前営業日日付)

スケジュール:
  - 起動時 (約20秒後): 取りこぼし catch-up（停止明けに最新日を確実に取得）
  - 毎営業日 08:30 JST: 取りこぼし catch-up（夜間取得失敗の保険）
  - 毎営業日 17:00 JST: Settlement CSV取得 + ローカル保存
  - 毎営業日 20:30 JST: OI XLSX + Market Data取得・マージ + ローカル保存
  - 毎営業日 21:00 JST: リトライ

取りこぼし対策 (catch-up):
  JPX Settlement/OI のエンドポイントは「最新営業日1日分」しかホストしないため、
  サーバーが止まっていた日のファイルは後から取得できない。起動時と毎朝に
  「ローカル最新日より新しく、かつ今まだ取得可能な営業日」を即ダウンロードして
  日々の取りこぼしを防ぐ（複数日の連続停止分は JPX 仕様上どうしても穴が残る）。
"""
import asyncio
import logging
import re
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

RB_FILE_RE = re.compile(r"rb(\d{8})\.csv")


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

    def _download_day(self, ds: str) -> bool:
        """指定営業日 (YYYYMMDD) の4ファイルをダウンロード。

        1つでも新規取得できれば True。既に全て存在する場合も True
        （_download_and_save が既存ファイルを True で返すため）。
        """
        got = False
        targets = [
            (LOCAL_DATA_DIR / f"rb{ds}.csv", SETTLEMENT_CSV_URL.format(date=ds)),
            (LOCAL_DATA_DIR / f"ose{ds}tp.csv", OSE_TP_URL.format(date=ds)),
            (LOCAL_DATA_DIR / f"{ds}open_interest.xlsx", OPEN_INTEREST_URL.format(date=ds)),
            (LOCAL_DATA_DIR / f"{ds}_market_data_whole_day.xlsx", MARKET_DATA_URL.format(date=ds)),
        ]
        for path, url in targets:
            if self._download_and_save(url, path):
                got = True
        return got

    def _latest_local_date(self) -> str | None:
        """ローカルに存在する rb{date}.csv の最新日付 (YYYYMMDD) を返す"""
        if not LOCAL_DATA_DIR.exists():
            return None
        dates = [
            m.group(1)
            for p in LOCAL_DATA_DIR.iterdir()
            if (m := RB_FILE_RE.match(p.name))
        ]
        return max(dates) if dates else None

    # ========== 取りこぼし catch-up ==========

    def _catchup_sync(self) -> None:
        """ローカル最新日より新しく、かつ今まだ JPX が公開している営業日を取得。

        JPX は最新営業日分しかホストしないため、停止明けに取得可能な分だけを
        確実に拾い、取れた場合のみデータを再ビルドする。
        """
        today = datetime.now(JST).date()
        latest_local = self._latest_local_date()
        new_dates = []

        # 新しい営業日から順に。ローカル最新日に達したら打ち切り。
        for i in range(7):
            d = today - timedelta(days=i)
            if d.weekday() >= 5:
                continue
            ds = d.strftime("%Y%m%d")
            if latest_local and ds <= latest_local:
                break
            if self._download_day(ds):
                new_dates.append(ds)

        if new_dates:
            service = self._import_service()
            result = service.get_data(force_refresh=True)
            date_val = (result or {}).get("data", {}).get("date", "?")
            logger.info(
                f"[NK225Options] Catch-up: downloaded {new_dates} "
                f"(latest_local was {latest_local}) → rebuilt to {date_val}"
            )
        else:
            logger.info(
                f"[NK225Options] Catch-up: already current "
                f"(latest_local={latest_local})"
            )

    def _settlement_sync(self) -> None:
        """Settlement CSV + ose*tp.csv 取得 → ローカル保存 → データ更新（同期）"""
        today = datetime.now(JST).date()

        # Try today and recent business days
        for i in range(3):
            d = today - timedelta(days=i)
            if d.weekday() >= 5:
                continue
            ds = d.strftime("%Y%m%d")

            rb_path = LOCAL_DATA_DIR / f"rb{ds}.csv"
            self._download_and_save(SETTLEMENT_CSV_URL.format(date=ds), rb_path)

            ose_path = LOCAL_DATA_DIR / f"ose{ds}tp.csv"
            self._download_and_save(OSE_TP_URL.format(date=ds), ose_path)

            if rb_path.exists() or ose_path.exists():
                break

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

    def _oi_merge_sync(self) -> None:
        """OI XLSX + Market Data 取得 → ローカル保存 → データ更新（同期）"""
        today = datetime.now(JST).date()

        # OI uses previous business day or current day
        for d in [today, _prev_business_day(today)]:
            ds = d.strftime("%Y%m%d")

            oi_path = LOCAL_DATA_DIR / f"{ds}open_interest.xlsx"
            self._download_and_save(OPEN_INTEREST_URL.format(date=ds), oi_path)

            md_path = LOCAL_DATA_DIR / f"{ds}_market_data_whole_day.xlsx"
            self._download_and_save(MARKET_DATA_URL.format(date=ds), md_path)

        service = self._import_service()
        logger.info("[NK225Options] Merging OI data...")
        result = service.get_data(force_refresh=True)
        if result and result.get("data"):
            logger.info("[NK225Options] OI merge completed")
        else:
            logger.warning("[NK225Options] OI merge returned empty")

    # ========== async ラッパー (blocking I/O は to_thread でループ外実行) ==========

    async def _run_catchup(self):
        try:
            await asyncio.to_thread(self._catchup_sync)
        except Exception as e:
            logger.error(f"[NK225Options] Catch-up error: {e}")
            import traceback
            traceback.print_exc()

    async def _run_settlement(self):
        try:
            await asyncio.to_thread(self._settlement_sync)
        except Exception as e:
            logger.error(f"[NK225Options] Error: {e}")
            import traceback
            traceback.print_exc()

    async def _run_oi_merge(self):
        try:
            await asyncio.to_thread(self._oi_merge_sync)
        except Exception as e:
            logger.error(f"[NK225Options] OI merge error: {e}")

    def start(self):
        # 起動時 catch-up (約20秒後に1回): 停止明けに最新日を確実に取得
        self.scheduler.add_job(
            self._run_catchup,
            "date",
            run_date=datetime.now(JST) + timedelta(seconds=20),
            id="nk225_options_catchup_startup",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        # 08:30 JST - 朝の catch-up (夜間取得失敗の保険)
        self.scheduler.add_job(
            self._run_catchup,
            CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone=JST),
            id="nk225_options_catchup_morning",
            replace_existing=True,
            misfire_grace_time=3600,
        )
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
        logger.info(
            "[NK225Options] Scheduler started "
            "(catch-up: startup + 08:30 | 17:00 + 20:30 + 21:00 JST)"
        )

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


nikkei225_options_scheduler = Nikkei225OptionsScheduler()
