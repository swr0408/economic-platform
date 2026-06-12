"""
Supply- and Demand-Driven PCE Inflation スケジューラー

SF Fed の PCE需給分解データを定期的にチェック。
実際の取得判定はサービス側の `_should_refresh()` が階層型ロジックで行う。

スケジュール（JST）:
- PCE発表直後のプロービング期: 23:00, 00:00, 01:00, 02:00, 03:00, 04:00
  （米国時PCE発表 22:30 JST の直後、SF Fed公開を1時間間隔で検知）
- 当日午後の通常リトライ期: 06:00, 10:00, 14:00, 18:00
- 翌日以降のフォールバック: 22:30（毎日固定）

サービス側 `_should_refresh()` の階層型判定:
- PCE発表0-6h:  1時間間隔
- PCE発表6-72h: 4時間間隔
- PCE発表72h+:  24時間間隔
- データ最新確認後: 次回PCE発表まで完全スキップ
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


class SupplyAndDemandPceScheduler:
    """SF Fed PCE需給分解スケジューラー"""

    # チェック時刻リスト (JST hour, minute)
    CHECK_TIMES = [
        (22, 30),  # PCE発表時刻（即時チェック）
        (23, 0),   # +30min
        (0, 0),    # +1.5h
        (1, 0),    # +2.5h
        (2, 0),    # +3.5h
        (3, 0),    # +4.5h
        (4, 0),    # +5.5h（プロービング期の最終）
        (6, 0),    # 通常リトライ
        (10, 0),
        (14, 0),
        (18, 0),
    ]

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._service = None
        self._is_running = False

    def _get_service(self):
        """サービスを取得（遅延ロード）"""
        if self._service is None:
            try:
                from backend.services.usa.supply_and_demand_driven_pce_inflation_service import (
                    supply_and_demand_driven_pce_inflation_service,
                )
            except ImportError:
                from services.usa.supply_and_demand_driven_pce_inflation_service import (
                    supply_and_demand_driven_pce_inflation_service,
                )
            self._service = supply_and_demand_driven_pce_inflation_service
        return self._service

    async def _check_and_fetch(self):
        """サービスの取得判定を呼ぶ（実際の取得判定はサービス側）"""
        try:
            logger.info("[SupplyDemandPCE] Triggering scheduled check...")
            service = self._get_service()
            # force_refresh=False で呼び、サービス側の _should_refresh() に判定を委ねる
            # 同期 requests/Excel 解析のためワーカースレッドへ退避（イベントループ保護）
            result = await asyncio.to_thread(service.get_data, force_refresh=False)
            source = result.get("source", "unknown")
            latest = result.get("latest", {}) or {}
            logger.info(
                f"[SupplyDemandPCE] Check complete: source={source}, "
                f"latest_date={latest.get('date')}"
            )
        except Exception as e:
            logger.error(f"[SupplyDemandPCE] Error in scheduled check: {e}")

    def start(self):
        """スケジューラーを開始"""
        if self._is_running:
            logger.info("[SupplyDemandPCE] Already running")
            return

        try:
            for hour, minute in self.CHECK_TIMES:
                self.scheduler.add_job(
                    self._check_and_fetch,
                    CronTrigger(hour=hour, minute=minute, timezone=JST),
                    id=f"supply_demand_pce_{hour:02d}{minute:02d}",
                    name=f"Supply/Demand PCE Check ({hour:02d}:{minute:02d} JST)",
                    replace_existing=True,
                    misfire_grace_time=600,
                )

            self.scheduler.start()
            self._is_running = True

            times_str = ", ".join(f"{h:02d}:{m:02d}" for h, m in self.CHECK_TIMES)
            logger.info(
                f"[SupplyDemandPCE] Started — check times: {times_str} JST "
                f"(service-side tiered retry: 1h/4h/24h based on PCE elapsed)"
            )

        except Exception as e:
            logger.error(f"[SupplyDemandPCE] Error starting scheduler: {e}")

    def shutdown(self):
        """スケジューラーを停止"""
        try:
            if self._is_running:
                self.scheduler.shutdown(wait=False)
                self._is_running = False
                logger.info("[SupplyDemandPCE] Shutdown")
        except Exception as e:
            logger.error(f"[SupplyDemandPCE] Error stopping scheduler: {e}")

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
            logger.error(f"[SupplyDemandPCE] Error in manual trigger: {e}")
            return {"status": "error", "reason": str(e)}


# シングルトンインスタンス
supply_and_demand_pce_scheduler = SupplyAndDemandPceScheduler()
