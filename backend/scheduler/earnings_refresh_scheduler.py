"""Earnings financial statements auto-refresh scheduler (Plan B: calendar-driven).

FMP決算カレンダーを参照し、直近に決算発表があった銘柄の財務諸表のみを
自動再取得することで、API呼び出しを最小化する。

スケジュール (JST):
  05:30  全国の決算カレンダーを再取得 (US AMC後、Asia BMO前)
  06:00  前日〜本日に発表があった銘柄の財務諸表を再取得
  18:00  Asia/EU の AMC 発表 + 当日 BMO の更新分を再取得

想定 API 消費:
  - カレンダー: 14ヵ国 × 1日 = 14 calls
  - 財務諸表:   発表銘柄 × 3 endpoints (IS/CF/BS)
                平均 5-15 銘柄/日 × 3 = 15-45 calls
  - 合計: ~30-60 calls/日 (FMP無料プラン 250/日 の範囲内)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import List, Tuple
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class EarningsRefreshScheduler:
    """決算財務諸表の自動更新スケジューラ"""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._is_running = False

    # ------------------------------------------------------------------
    # Service accessor
    # ------------------------------------------------------------------

    def _service(self):
        try:
            from services.earnings.earnings_service import (
                earnings_service,
                SUPPORTED_COUNTRIES,
                _COMPANIES,
            )
        except ImportError:
            from backend.services.earnings.earnings_service import (
                earnings_service,
                SUPPORTED_COUNTRIES,
                _COMPANIES,
            )
        return earnings_service, SUPPORTED_COUNTRIES, _COMPANIES

    # ------------------------------------------------------------------
    # Phase 1: refresh all calendars
    # ------------------------------------------------------------------

    def _refresh_all_calendars(self) -> None:
        """各国の決算カレンダーを再取得 (古いキャッシュを削除して即フェッチ)"""
        svc, countries, _ = self._service()
        start = datetime.now(JST)
        refreshed = 0
        errors = 0

        for c in countries:
            cc = c["code"]
            try:
                cache_path = svc._cache_path(cc, "calendar")
                cache_path.unlink(missing_ok=True)
                svc.get_calendar(cc)  # cache miss → forces fetch
                refreshed += 1
            except Exception as exc:
                logger.warning("[EarningsRefresh] calendar %s: %s", cc, exc)
                errors += 1

        elapsed = (datetime.now(JST) - start).total_seconds()
        logger.info(
            "[EarningsRefresh] Calendars refreshed: %d/%d in %.1fs (errors=%d)",
            refreshed, len(countries), elapsed, errors,
        )

    # ------------------------------------------------------------------
    # Phase 2: refresh financials for recently-released companies
    # ------------------------------------------------------------------

    def _find_targets(self) -> List[Tuple[str, str]]:
        """直近(昨日〜本日)に決算発表があった銘柄 [(country_code, display_ticker), ...]

        BMO/AMC 双方を捕捉するため 2日ウィンドウを採用。
        no_financials/fmp_ticker無しの銘柄は除外。
        """
        svc, countries, companies_by_cc = self._service()
        today = date.today()
        window = {today - timedelta(days=1), today}
        targets: List[Tuple[str, str]] = []

        for c in countries:
            cc = c["code"]
            try:
                cal = svc.get_calendar(cc)
            except Exception as exc:
                logger.warning("[EarningsRefresh] calendar read %s: %s", cc, exc)
                continue

            comps = {x["ticker"].upper(): x for x in companies_by_cc.get(cc, [])}

            for item in cal.get("items", []):
                d_str = item.get("date")
                sym = item.get("symbol")
                if not d_str or not sym:
                    continue
                try:
                    d = date.fromisoformat(d_str)
                except ValueError:
                    continue
                if d not in window:
                    continue
                comp = comps.get(sym.upper())
                if comp and not comp.get("no_financials") and comp.get("fmp_ticker"):
                    targets.append((cc, sym))

        return targets

    def _refresh_recent_financials(self) -> None:
        """対象銘柄の財務諸表キャッシュを削除 → 即再取得"""
        svc, _, _ = self._service()
        start = datetime.now(JST)
        targets = self._find_targets()

        if not targets:
            logger.info("[EarningsRefresh] No recent releases; skipping financials refresh")
            return

        ok = 0
        errors = 0
        for cc, sym in targets:
            try:
                cache_path = svc._cache_path(cc, f"financials_{sym.upper()}")
                cache_path.unlink(missing_ok=True)
                svc.get_financials(cc, sym)
                ok += 1
            except Exception as exc:
                logger.warning("[EarningsRefresh] %s/%s: %s", cc, sym, exc)
                errors += 1

        elapsed = (datetime.now(JST) - start).total_seconds()
        logger.info(
            "[EarningsRefresh] Financials refreshed: %d/%d in %.1fs (errors=%d) targets=%s",
            ok, len(targets), elapsed, errors,
            [f"{cc}:{sym}" for cc, sym in targets],
        )

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._is_running:
            return

        # 05:30 JST: refresh all calendars
        self.scheduler.add_job(
            self._refresh_all_calendars,
            CronTrigger(hour=5, minute=30),
            id="earnings_calendars",
            replace_existing=True,
        )

        # 06:00 JST: morning sweep (US AMC released previous evening + Asia BMO)
        self.scheduler.add_job(
            self._refresh_recent_financials,
            CronTrigger(hour=6, minute=0),
            id="earnings_financials_morning",
            replace_existing=True,
        )

        # 18:00 JST: evening sweep (Asia AMC + EU intra)
        self.scheduler.add_job(
            self._refresh_recent_financials,
            CronTrigger(hour=18, minute=0),
            id="earnings_financials_evening",
            replace_existing=True,
        )

        self.scheduler.start()
        self._is_running = True
        logger.info(
            "[EarningsRefresh] Started (05:30 calendars; 06:00/18:00 financials)"
        )

    def shutdown(self) -> None:
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False


earnings_refresh_scheduler = EarningsRefreshScheduler()
