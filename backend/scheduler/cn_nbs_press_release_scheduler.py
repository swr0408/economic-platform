"""
NBS プレスリリース 日次取込スケジューラー

毎日 JST 12:00 (北京時間 11:00、NBS 通常発表時刻 10:00 北京時間の1時間後) に
全 NBS 指標のプレスリリースを取得・DB蓄積し、手動更新CSVの差分も補填する。

これにより:
- ダッシュボード未訪問でも自動更新が走る
- バックエンドが一時的に停止しても、再開後に取りこぼし期間を遡って補完
- 手動更新CSVを更新するだけで自動でDB反映
"""
import asyncio
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


def _run_all_press_release_fetchers() -> dict:
    """全 NBS プレスリリース取込サービスを順次実行

    各サービスは内部で:
    - 直近6発表を巡回
    - DB既存月はスキップ
    - 不足月のExcelをDLしてDB UPSERT
    """
    results = {}

    fetchers = [
        ("gdp", "services.china.cn_gdp_growth_rate_service", "_fetch_and_upsert_from_press_release"),
        ("fixed_asset_investment", "services.china.cn_fixed_asset_investment_service", "_fetch_and_upsert_from_press_release"),
        ("industrial_production", "services.china.cn_industrial_production_service", "_fetch_and_upsert_from_press_release"),
        ("integrated_circuit", "services.china.cn_integrated_circuit_manufacturing_service", "_fetch_and_upsert_from_press_release"),
        ("retail_sales", "services.china.cn_retail_sales_service", "_fetch_and_upsert_from_press_release"),
        ("unemployment", "services.china.cn_unemployment_rate_service", "_fetch_and_upsert_from_press_release"),
    ]

    for name, module_path, fn_name in fetchers:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            fn = getattr(mod, fn_name)
            fn()
            results[name] = "ok"
        except Exception as e:
            logger.error(f"[NBSScheduler] {name} fetch failed: {e}")
            results[name] = f"error: {e}"

    # CPI/PPI/PMI/不動産 はサービスクラス内部で fetch するため、
    # 取込専用にダッシュボードビルドではなくサービスの _build_payload を呼ぶ
    payload_builders = [
        ("cpi", "services.china.cn_cpi_service", "cn_cpi_service", "_build_payload"),
        ("ppi", "services.china.cn_ppi_service", "cn_ppi_service", "_build_payload"),
        ("pmi", "services.china.cn_pmi_service", "cn_pmi_service", "_build_payload"),
        ("real_estate", "services.china.cn_commercial_residential_sales_service",
         "cn_commercial_residential_sales_service", "_build_payload"),
    ]

    for name, module_path, instance_name, fn_name in payload_builders:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            svc = getattr(mod, instance_name)
            fn = getattr(svc, fn_name)
            fn()
            results[name] = "ok"
        except Exception as e:
            logger.error(f"[NBSScheduler] {name} build failed: {e}")
            results[name] = f"error: {e}"

    return results


def _run_csv_backfill() -> dict:
    """manual_update CSV からの自動バックフィル"""
    try:
        from services.china.nbs_csv_backfill import backfill_csv
        return backfill_csv()
    except Exception as e:
        logger.error(f"[NBSScheduler] CSV backfill failed: {e}")
        return {"error": str(e)}


class CnNbsPressReleaseScheduler:
    """NBS プレスリリース日次取込スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._is_running = False

    async def _run(self):
        """全 NBS 指標を取込 → 続けて CSV バックフィル"""
        logger.info("[NBSScheduler] Starting daily press release fetch...")
        try:
            results = await asyncio.to_thread(_run_all_press_release_fetchers)
            logger.info(f"[NBSScheduler] Press release results: {results}")

            csv_results = await asyncio.to_thread(_run_csv_backfill)
            if csv_results:
                logger.info(f"[NBSScheduler] CSV backfill results: {csv_results}")

            logger.info("[NBSScheduler] Daily run completed")
        except Exception as e:
            logger.error(f"[NBSScheduler] Daily run failed: {e}", exc_info=True)

    def start(self):
        """スケジューラーを開始（毎日 JST 12:00）"""
        if self._is_running:
            logger.warning("[NBSScheduler] Already running")
            return

        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=12, minute=0, timezone=JST),
            id="nbs_press_release_daily",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        self._is_running = True
        logger.info("[NBSScheduler] Started (daily 12:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
            self._is_running = False
        except Exception:
            pass


cn_nbs_press_release_scheduler = CnNbsPressReleaseScheduler()
