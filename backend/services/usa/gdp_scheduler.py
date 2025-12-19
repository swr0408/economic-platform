#!/usr/bin/env python3
"""
GDP関連データ 自動更新スケジューラー

■ BEA GDP発表スケジュール更新（8:30 ET）:
  - GDP成長率（前期比年率）- FRED A191RL1Q225SBEA
  - GDP寄与度（5項目）- FRED各シリーズ
  - GDP項目別成長率 - BEA NIPA T10101
  発表時刻から10分間、毎分キャッシュを更新

■ 潜在成長率 日次更新（6:00 JST）:
  - 名目潜在成長率 - FRED NGDPPOT (pc1)
  - 実質潜在成長率 - FRED GDPPOT (pc1)

■ SLOOS（銀行貸し出し態度）四半期チェック（23:00 JST）:
  - 銀行貸し出し態度 - FRED DRTSCILM
  発表月: 2月、5月、8月、11月（日付は不定期、14:00 ET）
  各月1-25日に日次チェック、新データ検出後は当月のチェックをスキップ

■ BEAスケジュール更新: 年2回（1月5日、7月5日）
"""

import asyncio
from datetime import datetime, timedelta
from typing import List
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .gdp_service import gdp_service
from .gdp_contributions_service import gdp_contributions_service
from .bea_gdp_components_service import bea_gdp_components_service
from .bea_schedule_service import bea_schedule_service
from .potential_gdp_service import potential_gdp_service
from .bank_lending_service import bank_lending_service


class GDPScheduler:
    """GDP発表自動更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.service = gdp_service
        self.schedule_service = bea_schedule_service
        self.eastern = pytz.timezone('US/Eastern')
        # SLOOS更新済み月を記録（年-月形式）
        self._sloos_updated_months: set = set()

    async def update_gdp_data(self, release_date: datetime):
        """
        GDP関連データを全て更新
        - GDP成長率（前期比年率）
        - GDP寄与度（5項目）
        - GDP項目別成長率

        Args:
            release_date: GDP発表日
        """
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] Updating all GDP data for {release_date.strftime('%Y-%m-%d')}...")

        # 1. GDP成長率（FRED）
        try:
            result = self.service.get_gdp_growth_rate(force_refresh=True)
            if result.get("data"):
                print(f"[{timestamp}] GDP growth rate updated: {len(result['data'])} records")
            else:
                print(f"[{timestamp}] GDP growth rate update returned no data")
        except Exception as e:
            print(f"[{timestamp}] Error updating GDP growth rate: {e}")

        # 2. GDP寄与度（FRED）
        try:
            result = gdp_contributions_service.get_gdp_contributions(force_refresh=True)
            if result.get("data"):
                print(f"[{timestamp}] GDP contributions updated: {len(result['data'])} records")
            else:
                print(f"[{timestamp}] GDP contributions update returned no data")
        except Exception as e:
            print(f"[{timestamp}] Error updating GDP contributions: {e}")

        # 3. GDP項目別成長率（BEA NIPA）
        try:
            result = bea_gdp_components_service.get_gdp_components_growth(force_refresh=True)
            if result.get("data"):
                print(f"[{timestamp}] GDP components growth updated: {len(result['data'])} records")
            else:
                print(f"[{timestamp}] GDP components growth update returned no data")
        except Exception as e:
            print(f"[{timestamp}] Error updating GDP components growth: {e}")

    async def update_for_10_minutes(self, release_date: datetime):
        """
        発表時刻から10分間、毎分更新

        Args:
            release_date: GDP発表日時
        """
        print(f"[{datetime.now().isoformat()}] Starting 10-minute GDP update cycle for {release_date.strftime('%Y-%m-%d')}")

        # 10分間、毎分更新
        for i in range(10):
            await self.update_gdp_data(release_date)

            if i < 9:  # 最後の更新後は待機しない
                await asyncio.sleep(60)

        print(f"[{datetime.now().isoformat()}] Completed 10-minute GDP update cycle for {release_date.strftime('%Y-%m-%d')}")

    def schedule_gdp_updates(self):
        """
        全てのGDP発表日時の更新をスケジュール
        BEAスケジュールサービスから日程を取得
        """
        # BEAスケジュールから今後のGDP発表日を取得（12回分=約1年分）
        upcoming_gdp_releases = self.schedule_service.get_upcoming_gdp_releases(count=12)

        for release_info in upcoming_gdp_releases:
            try:
                # 日付をパース
                date_str = release_info["date"]  # YYYY-MM-DD形式
                release_date = datetime.strptime(date_str, "%Y-%m-%d")

                # 発表時刻は8:30 ET（米東部時間）
                release_datetime = self.eastern.localize(
                    release_date.replace(hour=8, minute=30, second=0)
                )

                # 現在時刻より未来の場合のみスケジュール
                now = datetime.now(self.eastern)
                if release_datetime > now:
                    # スケジューラーにジョブを追加
                    self.scheduler.add_job(
                        self.update_for_10_minutes,
                        trigger='date',
                        run_date=release_datetime,
                        args=[release_date],
                        id=f"gdp_update_{date_str}",
                        replace_existing=True
                    )

                    estimate_type = release_info.get("estimate_type", "unknown")
                    quarter = release_info.get("quarter", "?")
                    year = release_info.get("year", "?")
                    print(f"Scheduled GDP update for {date_str} Q{quarter}/{year} ({estimate_type}) at {release_datetime} (8:30 ET)")
                else:
                    print(f"Skipping past GDP release date: {date_str}")

            except Exception as e:
                print(f"Error scheduling GDP update for {release_info}: {e}")

    def schedule_bea_schedule_updates(self):
        """
        BEAスケジュールの年2回自動更新をスケジュール
        1月5日と7月5日の0:00 ETに実行
        """
        # 1月5日 0:00 ET
        self.scheduler.add_job(
            self._update_bea_schedule,
            trigger='cron',
            month='1',
            day='5',
            hour=0,
            minute=0,
            timezone=self.eastern,
            id='bea_schedule_update_jan',
            replace_existing=True
        )

        # 7月5日 0:00 ET
        self.scheduler.add_job(
            self._update_bea_schedule,
            trigger='cron',
            month='7',
            day='5',
            hour=0,
            minute=0,
            timezone=self.eastern,
            id='bea_schedule_update_jul',
            replace_existing=True
        )

        print("Scheduled BEA schedule auto-updates for January 5 and July 5")

    def schedule_potential_gdp_updates(self):
        """
        潜在成長率の日次更新をスケジュール
        日本時間6:00（米東部時間で16:00または17:00）に毎日実行
        """
        # 日本時間6:00 = UTC 21:00（前日）
        self.scheduler.add_job(
            self._update_potential_gdp,
            trigger='cron',
            hour=21,  # UTC 21:00 = JST 6:00
            minute=0,
            timezone='UTC',
            id='potential_gdp_daily_update',
            replace_existing=True
        )

        print("Scheduled potential GDP daily update at 6:00 JST")

    def schedule_sloos_updates(self):
        """
        SLOOS（銀行貸し出し態度）の四半期チェックをスケジュール
        発表月: 2月、5月、8月、11月（日付は不定期、14:00 ET）
        各月毎日チェック、新データ検出後は当月のチェックをスキップ

        チェック時刻: 23:00 JST（SLOOS発表は14:00 ET = 翌日4:00 JST夏/5:00 JST冬）
        """
        # 2,5,8,11月は毎日チェック（新データ検出後は当月スキップ）
        self.scheduler.add_job(
            self._check_and_update_bank_lending,
            trigger='cron',
            month='2,5,8,11',
            hour=14,  # UTC 14:00 = JST 23:00
            minute=0,
            timezone='UTC',
            id='sloos_quarterly_check',
            replace_existing=True
        )

        print("Scheduled SLOOS quarterly check for Feb/May/Aug/Nov daily at 23:00 JST")

    async def _check_and_update_bank_lending(self):
        """
        銀行貸し出し態度データをチェック
        - 当月すでに更新済みの場合はスキップ
        - キャッシュの最新日付より新しいデータがあれば更新し、当月を更新済みとしてマーク
        """
        try:
            now = datetime.now()
            timestamp = now.isoformat()
            current_month_key = f"{now.year}-{now.month:02d}"

            # 当月すでに更新済みならスキップ
            if current_month_key in self._sloos_updated_months:
                print(f"[{timestamp}] SLOOS already updated this month ({current_month_key}), skipping check")
                return

            print(f"[{timestamp}] Checking for new SLOOS data...")

            # 現在のキャッシュの最新日付を取得
            cache_status = bank_lending_service.get_cache_status()
            cached_latest = cache_status.get("latest")
            cached_latest_date = cached_latest.get("date") if cached_latest else None

            if cached_latest_date:
                print(f"[{timestamp}] Current cached SLOOS latest date: {cached_latest_date}")

            # 強制更新して最新データを取得
            result = bank_lending_service.get_bank_lending_standards(force_refresh=True)
            new_latest = result.get("latest")
            new_latest_date = new_latest.get("date") if new_latest else None

            if new_latest_date:
                if cached_latest_date and new_latest_date > cached_latest_date:
                    # 新データ検出 → 当月を更新済みとしてマーク
                    self._sloos_updated_months.add(current_month_key)
                    print(f"[{timestamp}] New SLOOS data found: {new_latest_date} (was {cached_latest_date})")
                    print(f"[{timestamp}] Marked {current_month_key} as updated, will skip remaining checks this month")
                elif cached_latest_date == new_latest_date:
                    print(f"[{timestamp}] SLOOS data is up to date: {new_latest_date}")
                else:
                    # 初回キャッシュ
                    self._sloos_updated_months.add(current_month_key)
                    print(f"[{timestamp}] SLOOS cache refreshed: {new_latest_date}")
            else:
                print(f"[{timestamp}] SLOOS check completed but no data returned")

        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Error checking SLOOS data: {e}")

    async def _update_potential_gdp(self):
        """潜在成長率データを更新"""
        try:
            timestamp = datetime.now().isoformat()
            print(f"[{timestamp}] Updating potential GDP data...")

            result = potential_gdp_service.fetch_potential_gdp(force_refresh=True)

            if result.get("real") or result.get("nominal"):
                print(f"[{timestamp}] Potential GDP updated: real={len(result.get('real', []))} nominal={len(result.get('nominal', []))} records")
            else:
                print(f"[{timestamp}] Potential GDP update returned no data")

        except Exception as e:
            print(f"[{timestamp}] Error updating potential GDP: {e}")

    async def _update_bea_schedule(self):
        """BEAスケジュールを更新し、GDPスケジュールを再登録"""
        try:
            print(f"[{datetime.now().isoformat()}] Updating BEA release schedule...")

            # BEAスケジュールを更新
            success = self.schedule_service.update_cache()

            if success:
                print(f"[{datetime.now().isoformat()}] BEA schedule updated successfully")

                # 古いGDPスケジュールをクリア
                self._clear_gdp_jobs()

                # 新しいスケジュールを登録
                self.schedule_gdp_updates()

                print(f"[{datetime.now().isoformat()}] GDP update schedule refreshed")
            else:
                print(f"[{datetime.now().isoformat()}] Failed to update BEA schedule")

        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Error updating BEA schedule: {e}")

    def _clear_gdp_jobs(self):
        """既存のGDP更新ジョブをクリア"""
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            if job.id.startswith("gdp_update_"):
                self.scheduler.remove_job(job.id)

    def start(self):
        """スケジューラーを開始"""
        # GDP発表スケジュールを登録（成長率、寄与度、項目別成長率）
        self.schedule_gdp_updates()

        # BEAスケジュールの年2回自動更新を登録
        self.schedule_bea_schedule_updates()

        # 潜在成長率の日次更新を登録
        self.schedule_potential_gdp_updates()

        # SLOOS（銀行貸し出し態度）の四半期更新を登録
        self.schedule_sloos_updates()

        self.scheduler.start()
        print("GDP Scheduler started")

    def shutdown(self):
        """スケジューラーを停止"""
        self.scheduler.shutdown()
        print("GDP Scheduler stopped")

    def get_scheduled_jobs(self) -> List[dict]:
        """スケジュール済みのジョブ一覧を取得"""
        jobs = self.scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]


# グローバルスケジューラーインスタンス
gdp_scheduler = GDPScheduler()
