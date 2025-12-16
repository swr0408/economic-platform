#!/usr/bin/env python3
"""
政策金利 自動更新スケジューラー
FOMC声明発表時刻（14:00 ET）から10分間、毎分キャッシュを更新
FRB公式スケジュールから日程を取得
"""

import asyncio
from datetime import datetime, timedelta
from typing import List
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .fred_service import fred_service
from .fomc_schedule_service import fomc_schedule_service


class PolicyRateScheduler:
    """政策金利自動更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.service = fred_service
        self.schedule_service = fomc_schedule_service
        self.eastern = pytz.timezone('US/Eastern')

    async def update_policy_rate(self, fomc_date: datetime):
        """
        政策金利データを更新
        Args:
            fomc_date: FOMC発表日
        """
        try:
            print(f"[{datetime.now().isoformat()}] Updating policy rate for FOMC {fomc_date.strftime('%Y-%m-%d')}...")

            # FRED APIからデータ取得（キャッシュを強制更新）
            result = self.service.get_policy_rate(force_refresh=True)

            if result.get("data"):
                status = self.service.get_cache_status("DFEDTARU")
                print(f"[{datetime.now().isoformat()}] Policy rate updated successfully: {len(result['data'])} records, cache: {status}")
            else:
                print(f"[{datetime.now().isoformat()}] Policy rate update returned no data: {result.get('error', 'unknown')}")

        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Error updating policy rate: {e}")

    async def update_for_10_minutes(self, fomc_date: datetime):
        """
        発表時刻から10分間、毎分更新
        Args:
            fomc_date: FOMC発表日時
        """
        print(f"[{datetime.now().isoformat()}] Starting 10-minute policy rate update cycle for {fomc_date.strftime('%Y-%m-%d')}")

        # 10分間、毎分更新
        for i in range(10):
            await self.update_policy_rate(fomc_date)

            if i < 9:  # 最後の更新後は待機しない
                await asyncio.sleep(60)

        print(f"[{datetime.now().isoformat()}] Completed 10-minute update cycle for {fomc_date.strftime('%Y-%m-%d')}")

    def schedule_fomc_updates(self):
        """
        全てのFOMC発表日時の更新をスケジュール
        FRB公式スケジュールから日程を取得
        """
        # FRB公式スケジュールから今後のFOMC日程を取得（全会合、16回分=2年分）
        upcoming_fomc_dates = self.schedule_service.get_upcoming_fomc_dates(count=16)

        for fomc_info in upcoming_fomc_dates:
            try:
                # 日付をパース
                date_str = fomc_info["date"]  # YYYYMMDD形式
                fomc_date = datetime.strptime(date_str, "%Y%m%d")

                # 発表時刻は14:00 ET（米東部時間）
                release_datetime = self.eastern.localize(
                    fomc_date.replace(hour=14, minute=0, second=0)
                )

                # 現在時刻より未来の場合のみスケジュール
                now = datetime.now(self.eastern)
                if release_datetime > now:
                    # 発表時刻（14:00 ET）にタスクを開始
                    trigger_time = release_datetime

                    # 日付文字列をYYYY-MM-DD形式に変換
                    date_str_formatted = fomc_date.strftime("%Y-%m-%d")

                    # スケジューラーにジョブを追加
                    self.scheduler.add_job(
                        self.update_for_10_minutes,
                        trigger='date',
                        run_date=trigger_time,
                        args=[fomc_date],
                        id=f"policy_rate_{date_str_formatted}",
                        replace_existing=True
                    )

                    sep_label = " (SEP)" if fomc_info.get("has_sep") else ""
                    print(f"Scheduled policy rate update for {fomc_info['label']}{sep_label} at {trigger_time} (14:00 ET)")
                else:
                    print(f"Skipping past FOMC date: {fomc_info['label']}")

            except Exception as e:
                print(f"Error scheduling policy rate update for {fomc_info}: {e}")

    def start(self):
        """スケジューラーを開始"""
        self.schedule_fomc_updates()
        self.scheduler.start()
        print("Policy Rate Scheduler started")

    def shutdown(self):
        """スケジューラーを停止"""
        self.scheduler.shutdown()
        print("Policy Rate Scheduler stopped")


# グローバルスケジューラーインスタンス
policy_rate_scheduler = PolicyRateScheduler()
