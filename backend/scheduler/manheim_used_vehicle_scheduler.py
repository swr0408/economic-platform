"""
Manheim Used Vehicle Value Index スケジューラー

Cox Automotive の Manheim Used Vehicle Value Index を定期的にチェック。
実際の取得判定はサービス側の `_should_refresh_manheim()` が行う:
- 毎月5日未満 → スキップ
- 対象月（先月）データ既に保持 → スキップ
- 最終試行から24時間未満 → スキップ
- 上記以外 → Cox スクレイピングして Excel 取得

スケジュール（JST）:
- 22:30, 01:00, 04:00 ← 米国営業時間中（ET 09:30, 12:00, 15:00）に対応
- 14:00 ← Cox営業時間外の予備

「1日1回」要件はサービス側の24時間スロットルで保証される。
複数の cron はネットワーク失敗時の冗長化目的。
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class ManheimUsedVehicleScheduler:
    """Manheim Used Vehicle Value Index スケジューラー"""

    # チェック時刻 (JST hour, minute)
    # サービス側の24時間スロットルで実際の取得は1日1回に制限される
    CHECK_TIMES = [
        (22, 30),  # 米国 ET 09:30（朝の発表に対応）
        (1, 0),    # 米国 ET 12:00（昼の発表に対応）
        (4, 0),    # 米国 ET 15:00（午後の発表に対応）
        (14, 0),   # 予備（朝の取得失敗時のリカバリ）
    ]

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service = None
        self._is_running = False

    def _get_service(self):
        """サービスを取得（遅延ロード）"""
        if self._service is None:
            try:
                from backend.services.usa.used_car_prices_service import (
                    used_car_prices_service,
                )
            except ImportError:
                from services.usa.used_car_prices_service import (
                    used_car_prices_service,
                )
            self._service = used_car_prices_service
        return self._service

    async def _check_and_fetch(self):
        """サービスの取得判定を呼ぶ（実際の更新判定はサービス側）"""
        try:
            logger.info("[ManheimUVVI] Triggering scheduled check...")
            service = self._get_service()
            # 同期スクレイピング/Excel 取得のためワーカースレッドへ退避（イベントループ保護）
            result = await asyncio.to_thread(service.get_data, force_refresh=False)
            source = result.get("source", "unknown")
            latest = result.get("latest", {}) or {}
            logger.info(
                f"[ManheimUVVI] Check complete: source={source}, "
                f"latest_date={latest.get('date')}"
            )
        except Exception as e:
            logger.error(f"[ManheimUVVI] Error in scheduled check: {e}")

    def start(self):
        """スケジューラーを開始"""
        if self._is_running:
            logger.info("[ManheimUVVI] Already running")
            return

        try:
            for hour, minute in self.CHECK_TIMES:
                self.scheduler.add_job(
                    self._check_and_fetch,
                    CronTrigger(hour=hour, minute=minute, timezone=JST),
                    id=f"manheim_uvvi_{hour:02d}{minute:02d}",
                    name=f"Manheim UVVI Check ({hour:02d}:{minute:02d} JST)",
                    replace_existing=True,
                    misfire_grace_time=600,
                )

            self.scheduler.start()
            self._is_running = True

            times_str = ", ".join(f"{h:02d}:{m:02d}" for h, m in self.CHECK_TIMES)
            logger.info(
                f"[ManheimUVVI] Started — check times: {times_str} JST "
                f"(service-side: skip if before day-5 / data current / <24h since last attempt)"
            )

        except Exception as e:
            logger.error(f"[ManheimUVVI] Error starting scheduler: {e}")

    def shutdown(self):
        """スケジューラーを停止"""
        try:
            if self._is_running:
                self.scheduler.shutdown(wait=False)
                self._is_running = False
                logger.info("[ManheimUVVI] Shutdown")
        except Exception as e:
            logger.error(f"[ManheimUVVI] Error stopping scheduler: {e}")

    def get_status(self) -> Dict[str, Any]:
        """スケジューラーのステータスを取得"""
        jobs = []
        if self._is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                })

        return {
            "running": self._is_running,
            "jobs": jobs,
            "check_times": self.CHECK_TIMES,
        }

    async def trigger_update(self) -> Dict[str, Any]:
        """手動更新トリガー"""
        try:
            service = self._get_service()
            # 同期 I/O のためワーカースレッドへ退避（FastAPI ループから呼ばれるため）
            result = await asyncio.to_thread(service.get_data, force_refresh=False)
            return {
                "status": "ok",
                "source": result.get("source"),
                "latest": result.get("latest"),
            }
        except Exception as e:
            logger.error(f"[ManheimUVVI] Error in manual trigger: {e}")
            return {"status": "error", "reason": str(e)}


# シングルトンインスタンス
manheim_used_vehicle_scheduler = ManheimUsedVehicleScheduler()
