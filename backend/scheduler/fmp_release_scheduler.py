"""
FMP発表日ベースの経済指標スケジューラー

FMP Economic Calendar APIから発表日を取得し、発表時刻の3分後にデータを取得する。
週1回、2ヶ月先までの発表日を取得してスケジュールを更新。

ハイブリッド方式:
1. メイン: FMP発表日の3分後にピンポイント取得
2. バックアップ: 週1回の発表日リフレッシュ（変更検知・漏れ防止）
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Set
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

try:
    from services.calendar.fmp_service import fmp_service
    from services.calendar.calendar_repository import calendar_repository
    from core.database import SessionLocal
except ImportError:
    from backend.services.calendar.fmp_service import fmp_service
    from backend.services.calendar.calendar_repository import calendar_repository
    from backend.core.database import SessionLocal


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# 発表後の更新設定
UPDATE_DELAY_MINUTES = 3  # 発表から3分後に取得開始
UPDATE_ITERATIONS = 3     # 3回取得（3分方式）
UPDATE_INTERVAL_SECONDS = 60

# FMP発表日取得設定
FUTURE_DAYS = 60  # 2ヶ月先まで取得

# 対象指標の設定
# fmp_event: FMP APIのeventパラメータに渡す値（完全一致検索用）
# fmp_event_pattern: イベント名のパターンマッチ用（部分一致）
FMP_INDICATOR_CONFIGS = [
    {
        "name_ja": "ISM製造業景況指数",
        "fmp_event": "ISM Manufacturing PMI",
        "fmp_event_pattern": "ISM Manufacturing PMI",
        "service_module": "services.usa.ism_manufacturing_service",
        "service_instance": "ism_manufacturing_service",
        "fetch_method": "get_ism_manufacturing_data",
    },
    {
        "name_ja": "ISM非製造業景況指数",
        "fmp_event": "ISM Services PMI",  # FMP APIでの正式名
        "fmp_event_pattern": "ISM Services PMI",
        "service_module": "services.usa.ism_non_manufacturing_service",
        "service_instance": "ism_non_manufacturing_service",
        "fetch_method": "get_ism_non_manufacturing_data",
    },
    {
        "name_ja": "CB消費者信頼感指数",
        "fmp_event": "CB Consumer Confidence",  # FMP APIでの正式名
        "fmp_event_pattern": "CB Consumer Confidence",
        "service_module": "services.usa.cb_consumer_confidence_service",
        "service_instance": "cb_consumer_confidence_service",
        "fetch_method": "get_cb_consumer_confidence_data",
    },
    {
        "name_ja": "Challenger人員削減数",
        "fmp_event": "Challenger Job Cuts",
        "fmp_event_pattern": "Challenger Job Cuts",
        "service_module": "services.usa.challenger_job_cuts_service",
        "service_instance": "challenger_job_cuts_service",
        "fetch_method": "get_challenger_data",
    },
    {
        "name_ja": "レッドブック",
        "fmp_event": "Redbook YoY",
        "fmp_event_pattern": "Redbook",
        "service_module": "services.usa.redbook_service",
        "service_instance": "redbook_service",
        "fetch_method": "get_redbook_data",
    },
    {
        "name_ja": "コントロールグループ",
        "fmp_event": "Retail Sales Ex Gas/Autos MoM",
        "fmp_event_pattern": "Retail Sales",
        "service_module": "services.usa.retail_control_service",
        "service_instance": "retail_control_service",
        "fetch_method": "get_retail_control_data",
    },
    {
        "name_ja": "輸入物価指数/輸出物価指数",
        "fmp_event": "Import Price Index MoM",
        "fmp_event_pattern": "Import Price",
        "service_module": "services.usa.import_export_price_service",
        "service_instance": "import_export_price_service",
        "fetch_method": "get_import_export_price_data",
    },
    {
        "name_ja": "銀行貸出態度調査（SLOOS）",
        "fmp_event": "Loan Officer Survey",
        "fmp_event_pattern": "Loan Officer",
        "service_module": "services.usa.bank_lending_service",
        "service_instance": "bank_lending_service",
        "fetch_method": "get_bank_lending_standards",
    },
]


class FMPReleaseScheduler:
    """
    FMP発表日ベースの経済指標スケジューラー

    FMPから将来の発表日を取得し、各発表の3分後にデータ取得ジョブをスケジュール。
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service_cache: Dict[str, Any] = {}
        self._scheduled_jobs: Set[str] = set()
        self._upcoming_releases: List[Dict[str, Any]] = []

    def _get_service_instance(self, config: Dict[str, Any]) -> Optional[Any]:
        """サービスインスタンスを動的にインポート"""
        import importlib

        cache_key = f"{config['service_module']}.{config['service_instance']}"

        if cache_key in self._service_cache:
            return self._service_cache[cache_key]

        module_paths = [
            f"backend.{config['service_module']}",
            config['service_module'],
        ]

        for module_path in module_paths:
            try:
                module = importlib.import_module(module_path)
                service = getattr(module, config['service_instance'])
                self._service_cache[cache_key] = service
                return service
            except (ImportError, AttributeError):
                continue

        return None

    def fetch_upcoming_releases_for_indicator(
        self,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        特定の指標の将来の発表日をFMPから取得（eventパラメータで絞り込み）

        Args:
            config: 指標設定

        Returns:
            発表予定リスト
        """
        name_ja = config["name_ja"]
        fmp_event = config["fmp_event"]

        today = date.today()
        end_date = today + timedelta(days=FUTURE_DAYS)

        try:
            # eventパラメータで指標を絞って取得
            events = fmp_service.fetch_calendar(
                today, end_date,
                country="US",
                event=fmp_event
            )
        except Exception as e:
            print(f"[FMPScheduler] Error fetching {name_ja}: {e}")
            return []

        releases = []
        seen_dates = set()
        now_jst = datetime.now(JST)

        for event in events:
            # 将来のイベントのみ（actualがない）
            if event.get("actual") is not None:
                continue

            datetime_raw = event.get("date", "")
            dt_utc, has_time = fmp_service.parse_datetime(datetime_raw)

            if not dt_utc:
                continue

            # 重複チェック（同日の複数イベント防止）
            date_key = dt_utc.date().isoformat()
            if date_key in seen_dates:
                continue
            seen_dates.add(date_key)

            # JSTに変換
            dt_jst = dt_utc.astimezone(JST)

            # 発表日が過去でないか確認
            if dt_jst <= now_jst:
                continue

            releases.append({
                "event_name": event.get("event", ""),
                "name_ja": name_ja,
                "datetime_utc": dt_utc,
                "datetime_jst": dt_jst,
                "has_time": has_time,
                "config": config,
                "estimate": event.get("estimate"),
            })

        return releases

    def fetch_all_upcoming_releases(self) -> List[Dict[str, Any]]:
        """
        全指標の将来の発表日を取得（各指標ごとにAPIを呼び出し）

        Returns:
            発表予定リスト [{event_name, datetime_utc, datetime_jst, config}, ...]
        """
        print(f"[FMPScheduler] Fetching upcoming releases for next {FUTURE_DAYS} days...")
        print(f"[FMPScheduler] Target indicators: {len(FMP_INDICATOR_CONFIGS)}")

        all_releases = []

        for config in FMP_INDICATOR_CONFIGS:
            releases = self.fetch_upcoming_releases_for_indicator(config)
            all_releases.extend(releases)
            if releases:
                print(f"  - {config['name_ja']}: {len(releases)} releases found")

        # 日時順にソート
        all_releases.sort(key=lambda x: x["datetime_utc"])

        print(f"[FMPScheduler] Total upcoming releases: {len(all_releases)}")
        for release in all_releases[:10]:  # 直近10件を表示
            print(f"    {release['name_ja']}: {release['datetime_jst'].strftime('%Y-%m-%d %H:%M JST')}")

        self._upcoming_releases = all_releases
        return all_releases

    def _sync_fmp_indicator_data(self, fmp_event: str, name_ja: str) -> int:
        """
        FMPから特定指標の直近イベントを取得してDBに同期（eventパラメータで絞り込み）

        Args:
            fmp_event: FMP APIのeventパラメータ値
            name_ja: 指標名（ログ用）

        Returns:
            Upsertしたレコード数
        """
        try:
            today = date.today()
            # 直近7日分を取得（発表後のactual値を拾う）
            start_date = today - timedelta(days=7)

            # eventパラメータで指標を絞って取得
            events = fmp_service.fetch_calendar(
                start_date, today,
                country="US",
                event=fmp_event
            )

            if not events:
                print(f"[FMPScheduler] No events found for: {name_ja}")
                return 0

            # 処理してDBにUpsert
            processed = [fmp_service.process_event(e) for e in events]
            count = calendar_repository.upsert_events(processed)

            print(f"[FMPScheduler] Synced {count} events for: {name_ja}")
            return count

        except Exception as e:
            print(f"[FMPScheduler] Error syncing {name_ja}: {e}")
            return 0

    async def fetch_indicator_data(
        self,
        config: Dict[str, Any],
        iteration: int = 1
    ):
        """
        指標データを取得（FMPからDB同期 → サービス経由で取得）

        Args:
            config: 指標設定
            iteration: 更新回数（1-3）
        """
        name_ja = config["name_ja"]
        fmp_event = config["fmp_event"]

        try:
            print(f"[FMPScheduler] Fetching {name_ja} (iteration {iteration}/{UPDATE_ITERATIONS})...")

            # Step 1: FMPから最新データを取得してDBに保存（eventパラメータで絞り込み）
            synced_count = self._sync_fmp_indicator_data(fmp_event, name_ja)
            print(f"[FMPScheduler] DB synced: {synced_count} events")

            # Step 2: サービス経由でデータを取得（DBから読み込み）
            service = self._get_service_instance(config)
            if service is None:
                print(f"[FMPScheduler] Service not found: {config['service_module']}")
                return

            fetch_method = getattr(service, config['fetch_method'], None)
            if fetch_method is None:
                print(f"[FMPScheduler] Method not found: {config['fetch_method']}")
                return

            # Redisキャッシュを無効化して再取得
            if hasattr(service, 'invalidate_cache'):
                service.invalidate_cache()

            result = fetch_method(force_refresh=True)

            if result and not result.get("error"):
                latest = result.get("latest", {})
                latest_date = latest.get("date") if latest else "N/A"
                latest_value = latest.get("value") if latest else "N/A"
                print(f"[FMPScheduler] ✓ {name_ja}: date={latest_date}, value={latest_value}, source={result.get('source')}")
            else:
                error = result.get("error") if result else "Unknown error"
                print(f"[FMPScheduler] ✗ {name_ja}: {error}")

        except Exception as e:
            print(f"[FMPScheduler] Error fetching {name_ja}: {e}")
            import traceback
            traceback.print_exc()

    async def update_indicator_for_3_minutes(self, config: Dict[str, Any]):
        """
        発表時刻から3分間、毎分データを取得（3分方式）

        Args:
            config: 指標設定
        """
        name_ja = config["name_ja"]
        print(f"[FMPScheduler] Starting 3-minute update cycle for: {name_ja}")

        for iteration in range(1, UPDATE_ITERATIONS + 1):
            await self.fetch_indicator_data(config, iteration)

            if iteration < UPDATE_ITERATIONS:
                await asyncio.sleep(UPDATE_INTERVAL_SECONDS)

        print(f"[FMPScheduler] Completed update cycle for: {name_ja}")

    def schedule_release_jobs(self):
        """
        全発表日のジョブをスケジュール（各指標ごとにFMP APIを呼び出し）
        """
        print("[FMPScheduler] Scheduling release jobs...")

        # 既存ジョブをクリア
        for job_id in list(self._scheduled_jobs):
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
        self._scheduled_jobs.clear()

        # 全指標の発表日を取得（指標ごとにeventパラメータで絞って取得）
        releases = self.fetch_all_upcoming_releases()

        scheduled_count = 0
        now_jst = datetime.now(JST)

        for release in releases:
            dt_jst = release["datetime_jst"]
            config = release["config"]
            name_ja = release["name_ja"]

            # 発表3分後にスケジュール
            trigger_time = dt_jst + timedelta(minutes=UPDATE_DELAY_MINUTES)

            if trigger_time <= now_jst:
                continue

            job_id = f"fmp_release_{name_ja}_{dt_jst.strftime('%Y%m%d_%H%M')}"

            self.scheduler.add_job(
                self.update_indicator_for_3_minutes,
                trigger=DateTrigger(run_date=trigger_time),
                args=[config],
                id=job_id,
                replace_existing=True
            )

            self._scheduled_jobs.add(job_id)
            scheduled_count += 1
            print(f"[FMPScheduler] Scheduled: {name_ja} at {trigger_time.strftime('%Y-%m-%d %H:%M JST')}")

        print(f"[FMPScheduler] Total jobs scheduled: {scheduled_count}")

    def schedule_weekly_refresh(self):
        """
        週次の発表日リフレッシュジョブを追加

        毎週日曜日 6:00 JSTに発表日を再取得してスケジュールを更新。
        """
        self.scheduler.add_job(
            self._refresh_schedules,
            trigger=CronTrigger(day_of_week='sun', hour=6, minute=0, timezone=JST),
            id="fmp_weekly_refresh",
            replace_existing=True
        )
        print("[FMPScheduler] Scheduled weekly refresh at Sun 06:00 JST")

        # 毎日深夜にも差分チェック（発表日変更検知用）
        self.scheduler.add_job(
            self._refresh_schedules,
            trigger=CronTrigger(hour=5, minute=0, timezone=JST),
            id="fmp_daily_refresh",
            replace_existing=True
        )
        print("[FMPScheduler] Scheduled daily refresh at 05:00 JST")

    async def _refresh_schedules(self):
        """スケジュールを再計算して更新"""
        print("[FMPScheduler] Refreshing release schedules...")
        self.schedule_release_jobs()

    def start(self):
        """スケジューラーを開始"""
        print("[FMPScheduler] ========================================")
        print("[FMPScheduler] Starting FMP Release Scheduler")
        print("[FMPScheduler] ========================================")

        self.schedule_release_jobs()
        self.schedule_weekly_refresh()
        self.scheduler.start()

        print("[FMPScheduler] Scheduler started successfully")
        self._print_status()

    def shutdown(self):
        """スケジューラーを停止"""
        print("[FMPScheduler] Shutting down FMP Release Scheduler...")
        self.scheduler.shutdown()
        print("[FMPScheduler] Scheduler stopped")

    def _print_status(self):
        """現在のスケジュール状態を表示"""
        jobs = self.scheduler.get_jobs()
        print(f"[FMPScheduler] Active jobs: {len(jobs)}")
        for job in jobs[:15]:  # 直近15件
            next_run = job.next_run_time
            if next_run:
                print(f"  - {job.id}: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    def get_status(self) -> Dict[str, Any]:
        """スケジューラーの状態を取得"""
        jobs = self.scheduler.get_jobs()

        return {
            "running": self.scheduler.running,
            "total_jobs": len(jobs),
            "upcoming_releases": len(self._upcoming_releases),
            "jobs": [
                {
                    "id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in jobs[:20]
            ],
        }

    def get_upcoming_releases(self) -> List[Dict[str, Any]]:
        """発表予定リストを取得"""
        return [
            {
                "name_ja": r["name_ja"],
                "event_name": r["event_name"],
                "datetime_jst": r["datetime_jst"].isoformat(),
                "estimate": r.get("estimate"),
            }
            for r in self._upcoming_releases
        ]


# グローバルスケジューラーインスタンス
fmp_release_scheduler = FMPReleaseScheduler()
