"""
ダッシュボードキャッシュ事前更新スケジューラー

定期的にダッシュボードのキャッシュを更新することで、
ユーザーのアクセス時の待ち時間を最小化する。

更新スケジュール:
- 日本時間 6:00, 12:00, 18:00, 23:00 に各ダッシュボードのキャッシュを更新
- 起動時にも一度キャッシュを更新（バックグラウンドで実行）
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


JST = ZoneInfo("Asia/Tokyo")


class DashboardCacheScheduler:
    """ダッシュボードキャッシュ事前更新スケジューラー"""

    # 更新対象のダッシュボード
    DASHBOARDS = [
        ("usa", "economy"),
        ("usa", "consumer"),
        ("usa", "employment"),
        ("usa", "inflation"),
        ("usa", "housing"),
        ("usa", "policy"),
    ]

    # 更新時刻（JST）
    UPDATE_HOURS = [6, 12, 18, 23]

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._is_running = False

    def _get_loader(self, country: str, category: str):
        """ダッシュボードローダーを取得"""
        try:
            from services.dashboard.registry import get_dashboard_loader
            return get_dashboard_loader(country, category)
        except ImportError:
            from backend.services.dashboard.registry import get_dashboard_loader
            return get_dashboard_loader(country, category)

    def _update_dashboard_cache(self, country: str, category: str) -> Dict[str, Any]:
        """
        ダッシュボードのキャッシュを更新（同期）

        Args:
            country: 国コード
            category: カテゴリコード

        Returns:
            更新結果
        """
        start_time = datetime.now(JST)
        print(f"[DashboardCache] Updating {country}/{category} cache...")

        try:
            loader = self._get_loader(country, category)
            if loader is None:
                return {
                    "success": False,
                    "country": country,
                    "category": category,
                    "error": "Loader not found",
                }

            # キャッシュを無効化せずに強制更新
            # ローダーのget_dataは内部でキャッシュ判定を行うが、
            # ここではキャッシュを先に無効化して新規取得させる
            loader.invalidate_cache()
            result = loader.get_data()

            elapsed = (datetime.now(JST) - start_time).total_seconds()
            print(f"[DashboardCache] {country}/{category} updated in {elapsed:.1f}s")

            return {
                "success": True,
                "country": country,
                "category": category,
                "cached": result.get("cached", False),
                "elapsed_seconds": elapsed,
            }

        except Exception as e:
            elapsed = (datetime.now(JST) - start_time).total_seconds()
            print(f"[DashboardCache] Error updating {country}/{category}: {e}")
            return {
                "success": False,
                "country": country,
                "category": category,
                "error": str(e),
                "elapsed_seconds": elapsed,
            }

    async def _update_all_dashboards(self):
        """全ダッシュボードのキャッシュを更新（非同期）"""
        print(f"[DashboardCache] Starting scheduled cache update at {datetime.now(JST).isoformat()}")

        loop = asyncio.get_event_loop()
        results = []

        # 順番に更新（並列だと外部API制限に引っかかる可能性があるため）
        for country, category in self.DASHBOARDS:
            try:
                result = await loop.run_in_executor(
                    self._executor,
                    self._update_dashboard_cache,
                    country,
                    category
                )
                results.append(result)
            except Exception as e:
                print(f"[DashboardCache] Exception updating {country}/{category}: {e}")
                results.append({
                    "success": False,
                    "country": country,
                    "category": category,
                    "error": str(e),
                })

        # 結果サマリー
        success_count = sum(1 for r in results if r.get("success"))
        print(f"[DashboardCache] Update complete: {success_count}/{len(results)} succeeded")

        return results

    def start(self):
        """スケジューラーを開始"""
        if self._is_running:
            print("[DashboardCache] Scheduler already running")
            return

        # 定期更新ジョブを追加（6:00, 12:00, 18:00, 23:00 JST）
        for hour in self.UPDATE_HOURS:
            self.scheduler.add_job(
                self._update_all_dashboards,
                CronTrigger(hour=hour, minute=0, timezone=JST),
                id=f"dashboard_cache_update_{hour}",
                name=f"Dashboard Cache Update ({hour}:00 JST)",
                replace_existing=True,
            )

        self.scheduler.start()
        self._is_running = True
        print(f"[DashboardCache] Scheduler started with updates at {self.UPDATE_HOURS} JST")

        # 起動時にバックグラウンドで初回更新を実行（5秒後に開始）
        self.scheduler.add_job(
            self._update_all_dashboards,
            "date",
            run_date=datetime.now(JST),
            id="dashboard_cache_initial",
            name="Dashboard Cache Initial Update",
        )

    def shutdown(self):
        """スケジューラーを停止"""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            print("[DashboardCache] Scheduler shutdown")

    def get_status(self) -> Dict[str, Any]:
        """スケジューラーのステータスを取得"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })

        return {
            "running": self._is_running,
            "jobs": jobs,
            "dashboards": self.DASHBOARDS,
            "update_hours": self.UPDATE_HOURS,
        }

    async def trigger_update(self, country: str = None, category: str = None) -> Dict[str, Any]:
        """
        手動でキャッシュ更新をトリガー

        Args:
            country: 国コード（省略時は全ダッシュボード）
            category: カテゴリコード（省略時は全ダッシュボード）

        Returns:
            更新結果
        """
        if country and category:
            # 特定のダッシュボードのみ更新
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._update_dashboard_cache,
                country,
                category
            )
            return {"results": [result]}
        else:
            # 全ダッシュボード更新
            results = await self._update_all_dashboards()
            return {"results": results}


# シングルトンインスタンス
dashboard_cache_scheduler = DashboardCacheScheduler()
