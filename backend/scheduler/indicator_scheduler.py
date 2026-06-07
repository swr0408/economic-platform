"""
経済指標バックグラウンドスケジューラー

発表時刻に合わせて自動的にデータを取得し、キャッシュを事前更新する。
これにより、ユーザーは発表直後にページをリロードしても即座にデータを取得できる。

動作ロジック:
1. 各指標の発表時刻をスケジュールチェッカーから計算
2. 発表時刻の1分前にジョブをスケジュール
3. 発表時刻から3分間、毎分データを取得（3分方式に対応）
4. 取得したデータはRedis + ファイルキャッシュに保存
"""

import asyncio
import importlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from .indicator_registry import (
    ALL_INDICATORS,
    IndicatorConfig,
    get_enabled_indicators,
    get_indicators_by_schedule_checker,
    Category
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# 発表後の更新回数（3分方式対応）
UPDATE_ITERATIONS = 3
UPDATE_INTERVAL_SECONDS = 60


class IndicatorScheduler:
    """
    経済指標バックグラウンドスケジューラー

    APSchedulerを使用して、各指標の発表時刻に合わせてデータを自動取得。
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service_cache: Dict[str, Any] = {}  # サービスインスタンスキャッシュ
        self._scheduled_jobs: Set[str] = set()  # スケジュール済みジョブID

    def _get_service_instance(self, config: IndicatorConfig) -> Optional[Any]:
        """
        サービスインスタンスを動的にインポート

        Args:
            config: 指標設定

        Returns:
            サービスインスタンス
        """
        cache_key = f"{config.service_module}.{config.service_instance}"

        if cache_key in self._service_cache:
            return self._service_cache[cache_key]

        # 複数のインポートパスを試行
        module_paths = [
            f"backend.{config.service_module}",  # backend.services.usa.xxx
            config.service_module,                # services.usa.xxx
        ]

        for module_path in module_paths:
            try:
                module = importlib.import_module(module_path)
                service = getattr(module, config.service_instance)
                self._service_cache[cache_key] = service
                return service
            except ImportError:
                continue
            except Exception as e:
                print(f"[Scheduler] Error importing {module_path}: {e}")
                continue

        print(f"[Scheduler] Failed to import service {config.service_module}.{config.service_instance}")
        return None

    def _get_schedule_checker(self, checker_name: str) -> Optional[Any]:
        """
        スケジュールチェッカーを動的にインポート

        Args:
            checker_name: チェッカー名（release_schedule_utils内）

        Returns:
            スケジュールチェッカーインスタンス
        """
        try:
            # 日本指標のチェッカーを先にチェック
            if checker_name.startswith("JAPAN_"):
                try:
                    import backend.services.japan.release_schedule_utils as japan_schedule_utils
                except ImportError:
                    import services.japan.release_schedule_utils as japan_schedule_utils
                return getattr(japan_schedule_utils, checker_name, None)

            # USAおよびその他の指標
            try:
                from backend.services.usa.release_schedule_utils import (
                    ReleaseScheduleChecker,
                    WageTrackerScheduleChecker,
                    NERPulseScheduleChecker,
                    VisaSpendingScheduleChecker,
                )
                import backend.services.usa.release_schedule_utils as schedule_utils
            except ImportError:
                from services.usa.release_schedule_utils import (
                    ReleaseScheduleChecker,
                    WageTrackerScheduleChecker,
                    NERPulseScheduleChecker,
                    VisaSpendingScheduleChecker,
                )
                import services.usa.release_schedule_utils as schedule_utils

            return getattr(schedule_utils, checker_name, None)
        except Exception as e:
            print(f"[Scheduler] Failed to get schedule checker {checker_name}: {e}")
            return None

    async def fetch_indicator_data(self, config: IndicatorConfig, iteration: int = 1):
        """
        指標データを取得（force_refresh=True）

        Args:
            config: 指標設定
            iteration: 更新回数（1-3）
        """
        try:
            service = self._get_service_instance(config)
            if service is None:
                print(f"[Scheduler] Service not found: {config.name}")
                return

            fetch_method = getattr(service, config.fetch_method, None)
            if fetch_method is None:
                print(f"[Scheduler] Method not found: {config.fetch_method}")
                return

            print(f"[Scheduler] Fetching {config.name} (iteration {iteration}/{UPDATE_ITERATIONS})...")

            # force_refresh=True でデータ取得。
            # fetch_method は requests 等のブロッキング I/O を行う同期関数のため、
            # 直接 await せずワーカースレッドへ退避する。これをしないと catchup や
            # 3分更新サイクルの一括取得がイベントループを占有し、ログイン等の
            # 全 HTTP リクエストがタイムアウトする（FRED 429 リトライ時に顕著）。
            result = await asyncio.to_thread(fetch_method, force_refresh=True)

            if result and not result.get("error"):
                latest = result.get("latest", {})
                latest_date = latest.get("date") if latest else "N/A"
                print(f"[Scheduler] ✓ {config.name}: latest={latest_date}, source={result.get('source')}")
            else:
                error = result.get("error") if result else "Unknown error"
                print(f"[Scheduler] ✗ {config.name}: {error}")

        except Exception as e:
            print(f"[Scheduler] Error fetching {config.name}: {e}")
            import traceback
            traceback.print_exc()

    async def update_indicator_for_3_minutes(self, configs: List[IndicatorConfig]):
        """
        発表時刻から3分間、毎分データを取得（3分方式対応）

        Args:
            configs: 同時発表の指標設定リスト
        """
        indicator_names = [c.name for c in configs]
        print(f"[Scheduler] Starting 3-minute update cycle for: {indicator_names}")

        for iteration in range(1, UPDATE_ITERATIONS + 1):
            # 全指標を並列取得
            tasks = [self.fetch_indicator_data(config, iteration) for config in configs]
            await asyncio.gather(*tasks, return_exceptions=True)

            if iteration < UPDATE_ITERATIONS:
                await asyncio.sleep(UPDATE_INTERVAL_SECONDS)

        print(f"[Scheduler] Completed update cycle for: {indicator_names}")

    def _get_next_release_time(self, checker: Any) -> Optional[datetime]:
        """
        スケジュールチェッカーから次回発表時刻を取得

        Args:
            checker: スケジュールチェッカーインスタンス

        Returns:
            次回発表時刻（JST）
        """
        try:
            status = checker.get_status()

            # 週次パターン
            if status.get("pattern") == "weekly":
                next_release_str = status.get("next_release")
                if next_release_str:
                    return datetime.fromisoformat(next_release_str)

            # 月内第N週パターン
            elif status.get("pattern") == "nth_week":
                next_release_str = status.get("next_release")
                if next_release_str:
                    return datetime.fromisoformat(next_release_str)

            # NER Pulse
            elif status.get("pattern") == "ner_pulse_weekly_excluding_monthly":
                next_release_str = status.get("next_release")
                if next_release_str:
                    return datetime.fromisoformat(next_release_str)

            # 賃金トラッカー（日次チェック）
            elif status.get("pattern") == "wage_tracker_daily_until_update":
                # 次のチェック時刻を計算
                now = datetime.now(JST)
                if now.day >= status.get("start_day", 1):
                    today_check = now.replace(
                        hour=9, minute=0, second=0, microsecond=0
                    )
                    if now < today_check:
                        return today_check
                    else:
                        return today_check + timedelta(days=1)
                return None

            # Visa Spending
            elif status.get("pattern") == "visa_spending_schedule":
                release_str = status.get("this_month_release")
                if release_str:
                    release_dt = datetime.fromisoformat(release_str)
                    now = datetime.now(JST)
                    if release_dt > now:
                        return release_dt
                return None

            # 毎営業日パターン（Inflation Nowcasting等）
            elif status.get("pattern") == "business_day_daily":
                next_release_str = status.get("next_release")
                if next_release_str:
                    return datetime.fromisoformat(next_release_str)
                return None

            # 日付範囲パターン（従来方式）
            elif status.get("pattern") == "date_range":
                release_time_str = status.get("release_time")
                if release_time_str and status.get("in_release_period"):
                    release_time = datetime.fromisoformat(release_time_str)
                    now = datetime.now(JST)
                    if release_time > now:
                        return release_time

            return None

        except Exception as e:
            print(f"[Scheduler] Error getting next release time: {e}")
            return None

    def schedule_indicator_jobs(self):
        """
        全指標のジョブをスケジュール

        同じ発表時刻の指標はグループ化して一括取得。
        """
        print("[Scheduler] Scheduling indicator jobs...")

        enabled_indicators = get_enabled_indicators()
        print(f"[Scheduler] Total enabled indicators: {len(enabled_indicators)}")

        # スケジュールチェッカー別にグループ化
        checker_groups: Dict[str, List[IndicatorConfig]] = {}
        for config in enabled_indicators:
            if not config.schedule_checker:
                continue

            checker_name = config.schedule_checker
            if checker_name not in checker_groups:
                checker_groups[checker_name] = []
            checker_groups[checker_name].append(config)

        print(f"[Scheduler] Schedule checker groups: {len(checker_groups)}")

        # 各グループに対してジョブをスケジュール
        scheduled_count = 0
        for checker_name, configs in checker_groups.items():
            try:
                checker = self._get_schedule_checker(checker_name)
                if checker is None:
                    print(f"[Scheduler] Checker not found: {checker_name}")
                    continue

                next_release = self._get_next_release_time(checker)
                if next_release is None:
                    # 日付範囲パターンの場合は、期間内の毎日チェック
                    status = checker.get_status() if hasattr(checker, 'get_status') else {}
                    if status.get("pattern") == "date_range":
                        self._schedule_daily_check(checker_name, configs)
                        scheduled_count += 1
                    continue

                # 発表時刻の1分前にスケジュール
                trigger_time = next_release - timedelta(minutes=1)
                now = datetime.now(JST)

                if trigger_time <= now:
                    # 既に過ぎている場合は次回をスケジュール
                    print(f"[Scheduler] Skipping past release: {checker_name} ({next_release})")
                    continue

                job_id = f"indicator_{checker_name}"
                indicator_names = [c.name for c in configs]

                self.scheduler.add_job(
                    self.update_indicator_for_3_minutes,
                    trigger=DateTrigger(run_date=trigger_time),
                    args=[configs],
                    id=job_id,
                    replace_existing=True
                )

                self._scheduled_jobs.add(job_id)
                scheduled_count += 1
                print(f"[Scheduler] Scheduled: {indicator_names} at {trigger_time.strftime('%Y-%m-%d %H:%M JST')}")

            except Exception as e:
                print(f"[Scheduler] Error scheduling {checker_name}: {e}")
                import traceback
                traceback.print_exc()

        print(f"[Scheduler] Total jobs scheduled: {scheduled_count}")

    def _schedule_daily_check(self, checker_name: str, configs: List[IndicatorConfig]):
        """
        日付範囲パターン用の毎日チェックジョブをスケジュール

        発表期間中、毎日発表時刻にジョブを実行。
        """
        try:
            checker = self._get_schedule_checker(checker_name)
            if checker is None:
                return

            status = checker.get_status()
            release_days = status.get("release_days")
            if not release_days:
                return

            start_day, end_day = release_days

            # 発表時刻を取得（サマータイム考慮）
            is_summer = status.get("is_dst", False)
            if is_summer:
                release_hour = getattr(checker, 'release_hour_summer', 21)
            else:
                release_hour = getattr(checker, 'release_hour_winter', 22)
            release_minute = getattr(checker, 'release_minute', 30)

            # Cronトリガーで期間中毎日実行
            job_id = f"indicator_daily_{checker_name}"

            # 日付範囲に応じたday_of_month設定
            if start_day <= end_day:
                day_range = f"{start_day}-{end_day}"
            else:
                # 月跨ぎの場合（例: 29-14）
                day_range = f"{start_day}-31,1-{end_day}"

            self.scheduler.add_job(
                self.update_indicator_for_3_minutes,
                trigger=CronTrigger(
                    day=day_range,
                    hour=release_hour,
                    minute=release_minute - 1,  # 1分前
                    timezone=JST
                ),
                args=[configs],
                id=job_id,
                replace_existing=True
            )

            self._scheduled_jobs.add(job_id)
            indicator_names = [c.name for c in configs]
            print(f"[Scheduler] Scheduled daily: {indicator_names} on days {day_range} at {release_hour}:{release_minute:02d} JST")

        except Exception as e:
            print(f"[Scheduler] Error scheduling daily check for {checker_name}: {e}")

    def schedule_recurring_jobs(self):
        """
        定期的にジョブスケジュールを更新するジョブを追加

        週次・月内第N週パターンの指標は、次回発表日時が変わるため
        定期的にスケジュールを再計算する必要がある。
        """
        # 毎日深夜0時にスケジュールを更新
        self.scheduler.add_job(
            self._refresh_schedules,
            trigger=CronTrigger(hour=0, minute=5, timezone=JST),
            id="refresh_schedules",
            replace_existing=True
        )
        print("[Scheduler] Scheduled daily schedule refresh at 00:05 JST")

    async def _refresh_schedules(self, retry_count: int = 0):
        """
        スケジュールを再計算して更新

        Args:
            retry_count: 現在のリトライ回数
        """
        MAX_RETRIES = 3
        RETRY_DELAY_SECONDS = 60

        print("[Scheduler] Refreshing indicator schedules...")

        try:
            # 既存のジョブを削除（refresh_schedulesを除く）
            for job_id in list(self._scheduled_jobs):
                try:
                    self.scheduler.remove_job(job_id)
                except Exception:
                    pass
            self._scheduled_jobs.clear()

            # 再スケジュール
            self.schedule_indicator_jobs()
            print("[Scheduler] Schedule refresh completed successfully")

        except Exception as e:
            print(f"[Scheduler] Error during schedule refresh: {e}")

            if retry_count < MAX_RETRIES:
                print(f"[Scheduler] Retrying in {RETRY_DELAY_SECONDS} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                await self._refresh_schedules(retry_count + 1)
            else:
                print(f"[Scheduler] Max retries ({MAX_RETRIES}) reached. Schedule refresh failed.")

    async def _catchup_missed_releases(self):
        """
        サーバー起動時に取得漏れを検出して即座にデータを取得

        過去24時間以内に発表があり、キャッシュが発表前の状態の指標を取得。
        """
        print("[Scheduler] ========================================")
        print("[Scheduler] Checking for missed releases...")
        print("[Scheduler] ========================================")

        enabled_indicators = get_enabled_indicators()
        checker_groups: Dict[str, List[IndicatorConfig]] = {}

        for config in enabled_indicators:
            if not config.schedule_checker:
                continue

            checker_name = config.schedule_checker
            if checker_name not in checker_groups:
                checker_groups[checker_name] = []
            checker_groups[checker_name].append(config)

        missed_indicators = []

        for checker_name, configs in checker_groups.items():
            try:
                checker = self._get_schedule_checker(checker_name)
                if checker is None:
                    continue

                # 各指標のキャッシュ状態を確認
                for config in configs:
                    service = self._get_service_instance(config)
                    if service is None:
                        continue

                    # キャッシュステータスを取得
                    get_cache_status = getattr(service, 'get_cache_status', None)
                    if get_cache_status is None:
                        continue

                    try:
                        cache_status = get_cache_status()
                        last_updated_str = cache_status.get("last_updated")

                        if last_updated_str:
                            # should_refreshで更新が必要か判定
                            should_refresh_method = getattr(checker, 'should_refresh', None)
                            if should_refresh_method and should_refresh_method(last_updated_str):
                                missed_indicators.append((config, checker_name))
                                print(f"[Scheduler] Missed release detected: {config.name}")
                        else:
                            # キャッシュがない場合も取得対象
                            missed_indicators.append((config, checker_name))
                            print(f"[Scheduler] No cache found: {config.name}")

                    except Exception as e:
                        print(f"[Scheduler] Error checking cache for {config.name}: {e}")

            except Exception as e:
                print(f"[Scheduler] Error processing checker {checker_name}: {e}")

        # 取得漏れがあれば即座に取得
        if missed_indicators:
            print(f"[Scheduler] Found {len(missed_indicators)} missed indicators. Fetching now...")

            # グループ化して並列取得
            configs_to_fetch = [config for config, _ in missed_indicators]

            # 最大10指標ずつ並列取得（サーバー負荷軽減）
            BATCH_SIZE = 10
            for i in range(0, len(configs_to_fetch), BATCH_SIZE):
                batch = configs_to_fetch[i:i + BATCH_SIZE]
                tasks = [self.fetch_indicator_data(config, 1) for config in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

                if i + BATCH_SIZE < len(configs_to_fetch):
                    await asyncio.sleep(5)  # バッチ間の待機

            print(f"[Scheduler] Catchup completed for {len(missed_indicators)} indicators")
        else:
            print("[Scheduler] No missed releases found")

    def start(self):
        """スケジューラーを開始"""
        print("[Scheduler] ========================================")
        print("[Scheduler] Starting Economic Indicator Scheduler")
        print("[Scheduler] ========================================")

        self.schedule_indicator_jobs()
        self.schedule_recurring_jobs()
        self.scheduler.start()

        # キャッチアップ処理をバックグラウンドで実行
        asyncio.create_task(self._catchup_missed_releases())

        print("[Scheduler] Scheduler started successfully")
        self._print_status()

    def shutdown(self):
        """スケジューラーを停止"""
        print("[Scheduler] Shutting down Economic Indicator Scheduler...")
        self.scheduler.shutdown()
        print("[Scheduler] Scheduler stopped")

    def _print_status(self):
        """現在のスケジュール状態を表示"""
        jobs = self.scheduler.get_jobs()
        print(f"[Scheduler] Active jobs: {len(jobs)}")
        for job in jobs:
            next_run = job.next_run_time
            if next_run:
                print(f"  - {job.id}: next run at {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    def get_status(self) -> Dict[str, Any]:
        """スケジューラーの状態を取得"""
        jobs = self.scheduler.get_jobs()

        return {
            "running": self.scheduler.running,
            "total_jobs": len(jobs),
            "jobs": [
                {
                    "id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in jobs
            ],
            "enabled_indicators": len(get_enabled_indicators()),
        }


# グローバルスケジューラーインスタンス
indicator_scheduler = IndicatorScheduler()
