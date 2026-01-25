"""
経済カレンダー スケジューラー

月2回（月初・月中）の定期更新 + 初回バックフィル
週1回の将来データ取得（次回発表日の予想値・発表時刻取得用）
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from backend.services.calendar.fmp_service import fmp_service
    from backend.services.calendar.calendar_repository import calendar_repository
except ImportError:
    from services.calendar.fmp_service import fmp_service
    from services.calendar.calendar_repository import calendar_repository


JST = ZoneInfo("Asia/Tokyo")


class CalendarScheduler:
    """経済カレンダーの定期更新スケジューラー"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=JST)
        self._is_running = False

    def start(self):
        """スケジューラーを開始"""
        if self._is_running:
            print("[CalendarScheduler] Already running")
            return

        # 月初（1日）JST 6:00
        self.scheduler.add_job(
            self._sync_calendar,
            CronTrigger(day=1, hour=6, minute=0, timezone=JST),
            id="calendar_sync_monthly_1st",
            name="Calendar Sync (1st of month)",
            replace_existing=True,
        )

        # 月中（15日）JST 6:00
        self.scheduler.add_job(
            self._sync_calendar,
            CronTrigger(day=15, hour=6, minute=0, timezone=JST),
            id="calendar_sync_monthly_15th",
            name="Calendar Sync (15th of month)",
            replace_existing=True,
        )

        # 毎日の差分更新（直近14日+将来7日を再取得）JST 7:00
        self.scheduler.add_job(
            self._sync_recent,
            CronTrigger(hour=7, minute=0, timezone=JST),
            id="calendar_sync_daily",
            name="Calendar Sync (Daily Recent)",
            replace_existing=True,
        )

        # 週1回の将来データ取得（毎週月曜 JST 6:30）
        # 次回発表日の予想値・発表時刻を事前に取得
        self.scheduler.add_job(
            self._sync_future,
            CronTrigger(day_of_week="mon", hour=6, minute=30, timezone=JST),
            id="calendar_sync_weekly_future",
            name="Calendar Sync (Weekly Future)",
            replace_existing=True,
        )

        self.scheduler.start()
        self._is_running = True
        print("[CalendarScheduler] Started - Monthly sync on 1st/15th, daily recent at 7:00, weekly future on Mon 6:30 JST")

    def stop(self):
        """スケジューラーを停止"""
        if not self._is_running:
            return

        self.scheduler.shutdown(wait=False)
        self._is_running = False
        print("[CalendarScheduler] Stopped")

    def _sync_calendar(self):
        """
        カレンダーを同期（過去1年分）

        月2回の定期実行用
        """
        print(f"[CalendarScheduler] Starting monthly sync at {datetime.now(JST).isoformat()}")

        try:
            today = date.today()
            start_date = today - timedelta(days=365)

            result = self.sync_range(start_date, today)

            print(f"[CalendarScheduler] Monthly sync completed:")
            print(f"  - Total events: {result['total_events']}")
            print(f"  - Upserted: {result['upserted_count']}")
            print(f"  - Duration: {result['duration_seconds']:.2f}s")

        except Exception as e:
            print(f"[CalendarScheduler] Monthly sync failed: {e}")
            import traceback
            traceback.print_exc()

    def _sync_recent(self):
        """
        直近14日+将来7日を再取得（改定データ拾い＋直近の将来イベント更新）

        毎日の定期実行用
        """
        print(f"[CalendarScheduler] Starting daily recent sync at {datetime.now(JST).isoformat()}")

        try:
            today = date.today()
            start_date = today - timedelta(days=14)
            end_date = today + timedelta(days=7)

            result = self.sync_range(start_date, end_date)

            print(f"[CalendarScheduler] Daily sync completed: {result['upserted_count']} events")

        except Exception as e:
            print(f"[CalendarScheduler] Daily sync failed: {e}")

    def _sync_future(self):
        """
        将来90日分を取得（次回発表日の予想値・発表時刻取得用）

        週1回の定期実行用
        """
        print(f"[CalendarScheduler] Starting weekly future sync at {datetime.now(JST).isoformat()}")

        try:
            today = date.today()
            end_date = today + timedelta(days=90)

            result = self.sync_range(today, end_date)

            print(f"[CalendarScheduler] Weekly future sync completed:")
            print(f"  - Total events: {result['total_events']}")
            print(f"  - Upserted: {result['upserted_count']}")
            print(f"  - Duration: {result['duration_seconds']:.2f}s")

        except Exception as e:
            print(f"[CalendarScheduler] Weekly future sync failed: {e}")
            import traceback
            traceback.print_exc()

    def sync_range(
        self,
        start_date: date,
        end_date: date,
        range_days: int = 90
    ) -> dict:
        """
        指定期間のカレンダーを同期

        Args:
            start_date: 開始日
            end_date: 終了日
            range_days: API呼び出し1回あたりの日数

        Returns:
            同期結果
        """
        started_at = datetime.utcnow()

        # FMPから取得
        events = fmp_service.fetch_calendar_ranges(start_date, end_date, range_days)

        # 対象国のみフィルタ
        filtered_events = fmp_service.filter_target_countries(events)

        # 処理してUpsert
        processed_events = [fmp_service.process_event(e) for e in filtered_events]
        upserted_count = calendar_repository.upsert_events(processed_events)

        # 指標候補を再集計
        calendar_repository.refresh_indicator_candidates("FMP")

        # 同期状態を更新
        calendar_repository.update_sync_state(
            provider="FMP",
            from_date=start_date,
            to_date=end_date,
            records_count=upserted_count,
        )

        completed_at = datetime.utcnow()

        return {
            "total_events": len(events),
            "filtered_events": len(filtered_events),
            "upserted_count": upserted_count,
            "duration_seconds": (completed_at - started_at).total_seconds(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

    def backfill(self, days: int = 365) -> dict:
        """
        初回バックフィル

        Args:
            days: 取得する日数（デフォルト365日=1年）

        Returns:
            バックフィル結果
        """
        print(f"[CalendarScheduler] Starting backfill for {days} days")

        today = date.today()
        start_date = today - timedelta(days=days)

        result = self.sync_range(start_date, today)

        # マッピング済み指標の発表履歴を同期
        mappings = calendar_repository.get_all_mappings()
        for mapping in mappings:
            try:
                count = calendar_repository.sync_indicator_releases(mapping["econalpha_id"])
                if count > 0:
                    print(f"[CalendarScheduler] Synced {count} releases for {mapping['econalpha_id']}")
            except Exception as e:
                print(f"[CalendarScheduler] Error syncing releases for {mapping['econalpha_id']}: {e}")

        print(f"[CalendarScheduler] Backfill completed: {result['upserted_count']} events")
        return result

    def run_now(self) -> dict:
        """手動で即時実行"""
        print("[CalendarScheduler] Manual sync triggered")
        return self.backfill(days=365)

    @property
    def is_running(self) -> bool:
        return self._is_running

    def get_next_run_times(self) -> dict:
        """次回実行時刻を取得"""
        if not self._is_running:
            return {"status": "Not scheduled"}

        result = {}

        for job_id in [
            "calendar_sync_monthly_1st",
            "calendar_sync_monthly_15th",
            "calendar_sync_daily",
            "calendar_sync_weekly_future",
        ]:
            job = self.scheduler.get_job(job_id)
            if job and job.next_run_time:
                result[job_id] = job.next_run_time.isoformat()
            else:
                result[job_id] = "Unknown"

        return result


# シングルトンインスタンス
calendar_scheduler = CalendarScheduler()
