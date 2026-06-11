#!/usr/bin/env python3
"""
FOMC Projections 自動更新スケジューラー
指定された発表時刻の10分後から10分間、毎分キャッシュを更新
FRB公式スケジュールから日程を取得
"""

import asyncio
from datetime import datetime, timedelta
from typing import List
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .fomc_projections_service import FOMCProjectionsService
from .fomc_table1_service import FOMCTable1Service
from .fomc_schedule_service import FOMCScheduleService


class FOMCProjectionsScheduler:
    """FOMC Projections自動更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.service = FOMCProjectionsService()
        self.table1_service = FOMCTable1Service()
        self.schedule_service = FOMCScheduleService()
        self.eastern = pytz.timezone('US/Eastern')
        self.update_tasks = {}  # 各発表日の更新タスクを管理

    async def update_projection(self, release_date: datetime):
        """
        FOMC Projectionsを更新 (Figure 2 と Table 1)
        Args:
            release_date: FOMC発表日
        """
        try:
            print(f"Updating FOMC Projections for {release_date.strftime('%Y-%m-%d')}")

            # Figure 2 (Dot Plot) を更新
            # update_figure_2 は requests + PDF描画 (fitz) のブロッキング処理。
            # ワーカースレッドへ退避しないとイベントループを占有し login 等が落ちる。
            result = await asyncio.to_thread(self.service.update_figure_2, release_date)

            if result["success"]:
                print(f"Successfully updated FOMC Projections Figure 2: {result['file_path']}")
                # 古いキャッシュをクリーンアップ (1年以上古いものを削除)
                deleted_count = self.service.clean_old_cache(keep_days=365)
                if deleted_count > 0:
                    print(f"Cleaned up {deleted_count} old Figure 2 cache files")
            else:
                print(f"Failed to update FOMC Projections Figure 2: {result.get('error')}")

            # Table 1 (Economic Projections) を更新（同じくブロッキング処理）
            table1_result = await asyncio.to_thread(self.table1_service.update_table_1, release_date)

            if table1_result["success"]:
                print(f"Successfully updated FOMC Projections Table 1: {table1_result['file_path']}")
                # 古いキャッシュをクリーンアップ
                deleted_count = self.table1_service.clean_old_cache(keep_days=365)
                if deleted_count > 0:
                    print(f"Cleaned up {deleted_count} old Table 1 cache files")
            else:
                print(f"Failed to update FOMC Projections Table 1: {table1_result.get('error')}")

        except Exception as e:
            print(f"Error updating FOMC Projections: {e}")

    async def update_for_10_minutes(self, release_date: datetime):
        """
        発表時刻から10分間、毎分更新
        Args:
            release_date: FOMC発表日時
        """
        # 10分間、毎分更新
        for i in range(10):
            await self.update_projection(release_date)

            if i < 9:  # 最後の更新後は待機しない
                await asyncio.sleep(60)

        print(f"Completed 10-minute update cycle for {release_date.strftime('%Y-%m-%d')}")

    def schedule_fomc_updates(self):
        """
        全てのFOMC発表日時の更新をスケジュール
        FRB公式スケジュールから日程を取得
        """
        # FRB公式スケジュールから今後のSEP発表日を取得
        upcoming_sep_dates = self.schedule_service.get_upcoming_sep_dates(count=8)

        for sep_info in upcoming_sep_dates:
            try:
                # 日付をパース
                date_str = sep_info["date"]  # YYYYMMDD形式
                release_date = datetime.strptime(date_str, "%Y%m%d")

                # 発表時刻は14:00 ET（米東部時間）
                release_datetime = self.eastern.localize(
                    release_date.replace(hour=14, minute=0, second=0)
                )

                # 現在時刻より未来の場合のみスケジュール
                now = datetime.now(self.eastern)
                if release_datetime > now:
                    # 発表時刻（14:00 ET）にタスクを開始
                    trigger_time = release_datetime

                    # 日付文字列をYYYY-MM-DD形式に変換
                    date_str_formatted = release_date.strftime("%Y-%m-%d")

                    # Cronトリガーで特定の日時に実行
                    self.scheduler.add_job(
                        self.update_for_10_minutes,
                        trigger='date',
                        run_date=trigger_time,
                        args=[release_datetime.replace(tzinfo=None)],  # タイムゾーン情報を削除
                        id=f"fomc_projections_{date_str_formatted}",
                        replace_existing=True
                    )

                    print(f"Scheduled FOMC Projections update for {sep_info['label']} at {trigger_time} (14:00 ET)")
                else:
                    print(f"Skipping past release date: {sep_info['label']}")

            except Exception as e:
                print(f"Error scheduling FOMC update for {sep_info}: {e}")

    def start(self):
        """スケジューラーを開始"""
        self.schedule_fomc_updates()
        self.scheduler.start()
        print("FOMC Projections Scheduler started")

    def shutdown(self):
        """スケジューラーを停止"""
        self.scheduler.shutdown()
        print("FOMC Projections Scheduler stopped")


# グローバルスケジューラーインスタンス
fomc_scheduler = FOMCProjectionsScheduler()
