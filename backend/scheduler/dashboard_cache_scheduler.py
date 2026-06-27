"""
ダッシュボードキャッシュ更新スケジューラー

2つの方式を組み合わせて、全指標を適切なタイミングで更新する。

A. イベント駆動ポーリング（15分ごと）:
   - FMPカレンダーDBをスキャンし、直近に発表があった国のダッシュボードのみ更新
   - 各ローダーの _is_cache_stale() が発表を検知した場合のみ load_all() 実行
   - 発表なしの国は DBクエリだけで即スキップ（軽量）

B. 発表集中帯スケジュール（フォールバック、全ダッシュボード対象）:
   JST
   07:30  NZ/AU 朝の発表後（NZ 06:45, AU 09:30 AEST = 07:30 JST 冬時間）
   09:30  JP 午前（統計局 08:30, 日銀 08:50）
   11:30  CN/AU/JP 昼前（CN 10:30-11:00, AU 11:00, JP 日銀 11:30）
   14:00  JP 午後（13:30 含む）
   17:30  EU 夕方（EU 16:00-17:00 夏時間）
   20:00  EU 夜（EU 19:00 夏時間, ECB）
   22:00  US 21:30 発表後
   00:30  US 0:00 発表後
   04:00  US 深夜（03:00 含む）+ 翌朝前の最終チェック
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Set
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# FMP国コード → ダッシュボード国コード
_FMP_TO_DASHBOARD = {
    "US": "usa",
    "JP": "japan",
    "GB": "uk", "UK": "uk",
    "EU": "eurozone", "DE": "eurozone", "FR": "eurozone", "ES": "eurozone",
    "CN": "china",
    "AU": "australia",
    "CA": "canada",
    "NZ": "newzealand",
    "CH": "switzerland",
    "IT": "eurozone",
    "TW": "global", "KR": "global",
}


class DashboardCacheScheduler:
    """ダッシュボードキャッシュ更新スケジューラー"""

    # 更新対象のダッシュボード（全国・全カテゴリ）
    DASHBOARDS = [
        # 米国
        ("usa", "economy"), ("usa", "consumer"), ("usa", "employment"),
        ("usa", "inflation"), ("usa", "housing"), ("usa", "policy"),
        # 日本
        ("japan", "economy"), ("japan", "consumer"), ("japan", "employment"),
        ("japan", "inflation"), ("japan", "policy"),
        # ユーロ圏
        ("eurozone", "economy"), ("eurozone", "consumer"), ("eurozone", "employment"),
        ("eurozone", "inflation"), ("eurozone", "policy"),
        # イギリス
        ("uk", "economy"), ("uk", "consumer"), ("uk", "employment"),
        ("uk", "inflation"), ("uk", "housing"), ("uk", "policy"),
        # オーストラリア
        ("australia", "economy"), ("australia", "consumer"), ("australia", "employment"),
        ("australia", "inflation"), ("australia", "housing"), ("australia", "policy"),
        # カナダ
        ("canada", "economy"), ("canada", "consumer"), ("canada", "employment"),
        ("canada", "inflation"), ("canada", "housing"), ("canada", "policy"),
        # 中国
        ("china", "economy"), ("china", "consumer"), ("china", "employment"),
        ("china", "inflation"), ("china", "housing"), ("china", "policy"),
        # スイス
        ("switzerland", "economy"), ("switzerland", "consumer"), ("switzerland", "employment"),
        ("switzerland", "inflation"), ("switzerland", "housing"), ("switzerland", "policy"),
        # ニュージーランド
        ("newzealand", "economy"), ("newzealand", "consumer"), ("newzealand", "employment"),
        ("newzealand", "inflation"), ("newzealand", "policy"),
        # グローバル
        ("global", "economy"),
    ]

    # 発表集中帯スケジュール (JST hour, minute)
    RELEASE_WAVE_HOURS = [
        (7, 30),   # NZ/AU 朝
        (9, 30),   # JP 午前
        (11, 30),  # CN/AU/JP 昼前
        (14, 0),   # JP 午後
        (17, 30),  # EU 夕方
        (20, 0),   # EU 夜
        (22, 0),   # US 21:30後
        (0, 30),   # US 0:00後
        (4, 0),    # US 深夜 + 翌朝最終
    ]

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._is_running = False

    def _get_loader(self, country: str, category: str):
        """ダッシュボードローダーを取得"""
        try:
            from services.dashboard.registry import get_dashboard_loader
            return get_dashboard_loader(country, category)
        except ImportError:
            from backend.services.dashboard.registry import get_dashboard_loader
            return get_dashboard_loader(country, category)

    # ------------------------------------------------------------------
    # コア: 1ダッシュボードの更新
    # ------------------------------------------------------------------

    def _update_dashboard_cache(self, country: str, category: str) -> Dict[str, Any]:
        """ダッシュボードのキャッシュを更新（同期）"""
        start_time = datetime.now(JST)

        try:
            loader = self._get_loader(country, category)
            if loader is None:
                return {"success": False, "country": country, "category": category,
                        "error": "Loader not found"}

            # get_data() 内で _is_cache_stale() が判定 → 発表なしならキャッシュ返却
            result = loader.get_data()

            elapsed = (datetime.now(JST) - start_time).total_seconds()
            was_stale = not result.get("cached", True)

            if was_stale:
                logger.info(f"[DashboardCache] {country}/{category} refreshed in {elapsed:.1f}s")
            return {"success": True, "country": country, "category": category,
                    "refreshed": was_stale, "elapsed_seconds": elapsed}

        except Exception as e:
            elapsed = (datetime.now(JST) - start_time).total_seconds()
            logger.error(f"[DashboardCache] Error {country}/{category}: {e}")
            return {"success": False, "country": country, "category": category,
                    "error": str(e), "elapsed_seconds": elapsed}

    # ------------------------------------------------------------------
    # A. イベント駆動ポーリング (15分ごと)
    # ------------------------------------------------------------------

    def _find_countries_with_recent_releases(self) -> Set[str]:
        """直近16分以内にFMPカレンダーで発表があった国を検出
        （15分間隔ポーリングに対して1分のオーバーラップで取り逃がし防止）"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
        except ImportError:
            from backend.core.database import SessionLocal
            from sqlalchemy import text

        try:
            now_utc = datetime.now(UTC)
            since_utc = now_utc - timedelta(minutes=16)

            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT DISTINCT country
                    FROM economic_calendar_events
                    WHERE datetime_utc > :since
                      AND datetime_utc <= :now
                """), {"since": since_utc, "now": now_utc}).fetchall()

            fmp_countries = {row[0] for row in rows}
            dashboard_countries = set()
            for fc in fmp_countries:
                dc = _FMP_TO_DASHBOARD.get(fc)
                if dc:
                    dashboard_countries.add(dc)

            return dashboard_countries

        except Exception as e:
            logger.warning(f"[DashboardCache] Event scan error: {e}")
            return set()

    def _sync_fmp_calendar_recent(self) -> None:
        """直近のFMPカレンダー（±数日）を即同期して actual を取り込む。

        economic_calendar_events の actual は calendar_scheduler の定期同期まで
        未取込（当日フラッシュ発表は翌朝07:00まで NULL）。発表検知時にFMPを即同期し、
        サービスが `actual IS NOT NULL` で当日分を落とすのを防ぐ。同期SQLのため
        呼び出し側はワーカースレッドで実行する。
        """
        try:
            from datetime import date
            from services.calendar.calendar_scheduler import calendar_scheduler
            today = date.today()
            calendar_scheduler.sync_range(today - timedelta(days=2), today + timedelta(days=1))
        except Exception as e:
            logger.warning(f"[DashboardCache] FMP calendar recent sync failed: {e}")

    async def _event_driven_poll(self):
        """イベント駆動ポーリング: 直近に発表があった国のダッシュボードのみ更新"""
        # 同期 SQLAlchemy クエリのためワーカースレッドへ退避（イベントループ保護）
        countries = await asyncio.to_thread(self._find_countries_with_recent_releases)
        if not countries:
            return

        # 発表検知時はFMPカレンダーを即同期して当日発表の actual を取り込む
        # （定期同期待ちだと actual=NULL のまま更新され当月分が欠落する）。
        # 同期で新たに actual が判明する国もあるため再検出して和集合を取る。
        await asyncio.to_thread(self._sync_fmp_calendar_recent)
        countries |= await asyncio.to_thread(self._find_countries_with_recent_releases)

        logger.info(f"[DashboardCache] Event-driven: releases detected for {countries}")

        loop = asyncio.get_event_loop()
        refreshed = 0
        for country, category in self.DASHBOARDS:
            if country not in countries:
                continue
            try:
                result = await loop.run_in_executor(
                    self._executor, self._update_dashboard_cache, country, category
                )
                if result.get("refreshed"):
                    refreshed += 1
            except Exception as e:
                logger.warning(f"[DashboardCache] Event poll error {country}/{category}: {e}")

        if refreshed > 0:
            logger.info(f"[DashboardCache] Event-driven: {refreshed} dashboards refreshed")

    # ------------------------------------------------------------------
    # B. 発表集中帯フォールバック (全ダッシュボード)
    # ------------------------------------------------------------------

    async def _update_all_dashboards(self):
        """全ダッシュボードのキャッシュを更新（非同期）"""
        logger.info(f"[DashboardCache] Release-wave update at {datetime.now(JST).strftime('%H:%M')}")

        loop = asyncio.get_event_loop()
        refreshed = 0
        errors = 0

        for country, category in self.DASHBOARDS:
            try:
                result = await loop.run_in_executor(
                    self._executor, self._update_dashboard_cache, country, category
                )
                if result.get("refreshed"):
                    refreshed += 1
                if not result.get("success"):
                    errors += 1
            except Exception as e:
                logger.warning(f"[DashboardCache] Error {country}/{category}: {e}")
                errors += 1

        logger.info(
            f"[DashboardCache] Release-wave complete: "
            f"{refreshed} refreshed, {errors} errors, "
            f"{len(self.DASHBOARDS) - refreshed - errors} cache-hit"
        )

    # ------------------------------------------------------------------
    # 起動 / 停止
    # ------------------------------------------------------------------

    def start(self):
        """スケジューラーを開始"""
        if self._is_running:
            logger.info("[DashboardCache] Already running")
            return

        # A. イベント駆動ポーリング: 毎時 00, 15, 30, 45分
        self.scheduler.add_job(
            self._event_driven_poll,
            CronTrigger(minute="0,15,30,45", timezone=JST),
            id="dashboard_event_poll",
            name="Dashboard Event-Driven Poll (every 15min)",
            replace_existing=True,
            misfire_grace_time=300,
        )

        # B. 発表集中帯スケジュール: 各時間帯に全ダッシュボード
        for hour, minute in self.RELEASE_WAVE_HOURS:
            self.scheduler.add_job(
                self._update_all_dashboards,
                CronTrigger(hour=hour, minute=minute, timezone=JST),
                id=f"dashboard_wave_{hour:02d}{minute:02d}",
                name=f"Dashboard Release Wave ({hour:02d}:{minute:02d} JST)",
                replace_existing=True,
                misfire_grace_time=1800,
            )

        self.scheduler.start()
        self._is_running = True

        wave_times = ", ".join(f"{h:02d}:{m:02d}" for h, m in self.RELEASE_WAVE_HOURS)
        logger.info(
            f"[DashboardCache] Started — "
            f"event poll: 15min interval, "
            f"release waves: {wave_times} JST"
        )

        # 起動時にバックグラウンドで初回更新
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
            logger.info("[DashboardCache] Shutdown")

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
            "dashboards_count": len(self.DASHBOARDS),
            "release_wave_hours": self.RELEASE_WAVE_HOURS,
        }

    async def trigger_update(self, country: str = None, category: str = None) -> Dict[str, Any]:
        """手動でキャッシュ更新をトリガー"""
        if country and category:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, self._update_dashboard_cache, country, category
            )
            return {"results": [result]}
        else:
            results = await self._update_all_dashboards()
            return {"results": results}


# シングルトンインスタンス
dashboard_cache_scheduler = DashboardCacheScheduler()
