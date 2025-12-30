"""
市場データスケジューラー
毎日JST 6:00に全銘柄の日足データを更新
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from services.market.yfinance_service_db import yfinance_service_db
except ImportError:
    from backend.services.market.yfinance_service_db import yfinance_service_db


JST = ZoneInfo("Asia/Tokyo")


class MarketDataScheduler:
    """市場データの定期更新スケジューラー"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=JST)
        self._is_running = False

    def start(self):
        """スケジューラーを開始"""
        if self._is_running:
            print("[MarketScheduler] Already running")
            return

        # 毎日JST 6:00に実行
        self.scheduler.add_job(
            self._update_daily_data,
            CronTrigger(hour=6, minute=0, timezone=JST),
            id="market_daily_update",
            name="Market Daily Data Update",
            replace_existing=True,
        )

        # 土日を除く毎日JST 7:00にも実行（再試行）
        self.scheduler.add_job(
            self._update_daily_data_retry,
            CronTrigger(hour=7, minute=0, day_of_week="mon-fri", timezone=JST),
            id="market_daily_update_retry",
            name="Market Daily Data Update (Retry)",
            replace_existing=True,
        )

        self.scheduler.start()
        self._is_running = True
        print("[MarketScheduler] Started - Daily update scheduled at JST 6:00")

    def stop(self):
        """スケジューラーを停止"""
        if not self._is_running:
            return

        self.scheduler.shutdown(wait=False)
        self._is_running = False
        print("[MarketScheduler] Stopped")

    def _update_daily_data(self):
        """日足データを更新"""
        print(f"[MarketScheduler] Starting daily update at {datetime.now(JST).isoformat()}")

        try:
            result = yfinance_service_db.update_all_symbols(force_refresh=True)

            print(f"[MarketScheduler] Update completed:")
            print(f"  - Success: {result['success_count']}/{result['total']}")
            print(f"  - Failed: {result['failed_count']}")
            print(f"  - Duration: {result['duration_seconds']:.2f}s")

            if result["errors"]:
                print(f"  - Errors:")
                for err in result["errors"][:5]:  # 最初の5件のみ表示
                    print(f"    {err}")

        except Exception as e:
            print(f"[MarketScheduler] Update failed: {e}")
            import traceback
            traceback.print_exc()

    def _update_daily_data_retry(self):
        """失敗した銘柄のみ再試行"""
        print(f"[MarketScheduler] Retry update at {datetime.now(JST).isoformat()}")

        try:
            # 最新データがない or 古い銘柄のみ更新
            result = yfinance_service_db.update_all_symbols(force_refresh=False)

            if result["success_count"] > 0:
                print(f"[MarketScheduler] Retry completed: {result['success_count']} updated")

        except Exception as e:
            print(f"[MarketScheduler] Retry failed: {e}")

    def run_now(self, force_refresh: bool = True):
        """手動で即時実行"""
        print(f"[MarketScheduler] Manual update triggered")
        return yfinance_service_db.update_all_symbols(force_refresh)

    @property
    def is_running(self) -> bool:
        return self._is_running

    def get_next_run_time(self) -> str:
        """次回実行時刻を取得"""
        if not self._is_running:
            return "Not scheduled"

        job = self.scheduler.get_job("market_daily_update")
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return "Unknown"


# シングルトンインスタンス
market_scheduler = MarketDataScheduler()
