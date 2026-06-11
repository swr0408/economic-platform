"""
マーケットデータ スケジューラー

専用スケジューラーを持たないマーケットサービスをバックグラウンドで定期更新する。
アクセス駆動（TTL依存）のみだと、未アクセス時にデータが古くなる問題を防止する。

スケジュール（すべて JST、平日のみ ※特記を除く）:
  ─ 日次 ─
  07:00  US_CLOSE — 米国市場クローズ後（yfinance US系、CBOE、VIX、CNN F&G等）
  09:00  US_CLOSE_RETRY — リトライ
  16:30  JP_CLOSE — 東京市場クローズ後（JPX PCR、騰落、MOF、日経バリュエーション等）
  20:30  JP_CLOSE_RETRY — リトライ（JPX OI 含む）

  ─ 週次 ─
  木 00:00  EIA_WEEKLY — EIA原油/ガソリン/留出油在庫（水曜 10:30 ET 発表）
  金 00:00  EIA_GAS — EIA天然ガス貯蔵（木曜 10:30 ET 発表）
  金 08:00  NAAIM — NAAIM Exposure（木曜米国発表）
  土 06:00  CFTC — CFTC Positioning / Baker Hughes Rig Count（金曜 15:30 ET 発表）
  水 12:00  API_CRUDE — API原油在庫（火曜 21:30 EST 発表）

  ─ 月次 ─
  1-15日 08:00  MONTHLY_EARLY — TSMC売上、LBMA、EIA STEO
  10-22日 08:00  MONTHLY_MID — OPEC MOMR、IEA OMR（手動Excel配置検出）
  20-28日 08:00  MONTHLY_LATE — Eurostat天然ガス生産、EIA天然ガス貿易/LNG

既にスケジューラーを持つサービスは除外:
  comex_gold/silver/copper, gold_etf_holdings, wgc_gold_etf, gold_premium,
  sge_gold, china_gold_etf_balance, nikkei225_options, ny_option_cut,
  jpx_investor_trading
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from backend.core.redis_client import redis_client
except ImportError:
    from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# 起動時キャッチアップ判定用 Redis マーカー
_CATCHUP_MARKER_PREFIX = "market_data_scheduler:last_run:"


def _set_run_marker(label: str) -> None:
    """バッチ実行完了後に呼ぶ。次回起動時の age 判定に使う。"""
    try:
        redis_client.set(
            f"{_CATCHUP_MARKER_PREFIX}{label}",
            {"ts": datetime.now(JST).isoformat()},
            expire=0,
        )
    except Exception as e:
        logger.warning(f"[MarketScheduler] Failed to set marker {label}: {e}")


def _get_run_marker_age_hours(label: str) -> float | None:
    """マーカーから前回実行からの経過時間 (h) を返す。マーカーなしは None。"""
    try:
        cached = redis_client.get(f"{_CATCHUP_MARKER_PREFIX}{label}")
        if not cached:
            return None
        ts_str = cached.get("ts") if isinstance(cached, dict) else None
        if not ts_str:
            return None
        last_run = datetime.fromisoformat(ts_str)
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=JST)
        return (datetime.now(JST) - last_run).total_seconds() / 3600
    except Exception as e:
        logger.warning(f"[MarketScheduler] Failed to read marker {label}: {e}")
        return None


# ---------------------------------------------------------------------------
# サービス定義（モジュールパス, シングルトン名, メソッド名）
# ---------------------------------------------------------------------------

# ── 日次: 米国市場クローズ後 (07:00 + 09:00 JST 平日) ──
US_CLOSE_SERVICES = [
    # Sentiment
    ("services.market.fear_greed_service", "fear_greed_service", "get_fear_greed_data"),
    ("services.market.gex_dix_service", "gex_dix_service", "get_gex_dix_data"),
    ("services.market.cboe_pcr_service", "cboe_pcr_service", "get_data"),
    # Volatility / Ratios
    ("services.market.vix_futures_curve_service", "vix_futures_curve_service", "get_data"),
    ("services.market.vix_cross_ratio_service", "vix_cross_ratio_service", "get_data"),
    ("services.market.historical_volatility_service", "historical_volatility_service", "get_data"),
    ("services.market.sector_ratio_service", "sector_ratio_service", "get_data"),
    ("services.market.copper_to_gold_ratio_service", "copper_to_gold_ratio_service", "get_data"),
    ("services.market.russell2000_russell1000_service", "russell2000_russell1000_service", "get_data"),
    ("services.market.nt_magnification_service", "nt_magnification_service", "get_data"),
    ("services.market.cmdi_service", "cmdi_service", "get_data"),
    # Valuation (US)
    ("services.market.sp500_valuation_service", "sp500_valuation_service", "get_data"),
    ("services.market.nasdaq100_valuation_service", "nasdaq100_valuation_service", "get_data"),
    # Rates / Credit
    ("services.market.us_interest_rate_spread_service", "us_interest_rate_spread_service", "get_data"),
    ("services.market.financial_stress_index_service", "financial_stress_index_service", "get_data"),
    # Metals (LME ロンドン17:00 GMT = 02:00 JST、Silver ETF)
    # NOTE: COMEX copper は CME XLS が 403 のため JSON サービスは停滞中。
    # 表示は comex_warehouse_screenshot_service (MacroMicro) に切替済み。
    ("services.market.lme_copper_stock_service", "lme_copper_stock_service", "get_data"),
    ("services.market.silver_etf_holdings_service", "silver_etf_holdings_service", "get_data"),
    # Energy (yfinance daily)
    ("services.market.crude_oil_yoy_service", "crude_oil_yoy_service", "get_data"),
    ("services.market.natural_gas_yoy_service", "natural_gas_yoy_service", "get_data"),
    ("services.market.crack_spread_service", "crack_spread_service", "get_data"),
    # EU Gas (AGSI 日次、前日深夜更新)
    ("services.market.eu_natural_gas_storage_service", "eu_natural_gas_storage_service", "get_data"),
    # NOAA HDD/CDD (日次)
    ("services.market.noaa_hdd_cdd_service", "noaa_hdd_cdd_service", "get_data"),
    # Adjustments (EIA monthly, 6h TTL)
    ("services.market.adjustments_service", "adjustments_service", "get_data"),
]

# ── 日次: 東京市場クローズ後 (16:30 + 20:30 JST 平日) ──
JP_CLOSE_SERVICES = [
    # JPX PCR (取引高: 当日夕、建玉: 20:00頃公開)
    ("services.market.jpx_pcr_service", "jpx_pcr_service", "get_data"),
    # 騰落レシオ (東証引け後)
    ("services.market.advance_decline_ratio_service", "advance_decline_ratio_service", "get_data"),
    # 日経関連
    ("services.market.nikkei_regression_service", "nikkei_regression_service", "get_data"),
    ("services.market.nikkei_yoy_service", "nikkei_yoy_service", "get_data"),
    ("services.market.nikkei_double_inverse_service", "nikkei_double_inverse_service", "get_data"),
    ("services.market.sq_analysis_service", "SqAnalysisService", "get_data"),
    # Valuation (JP)
    ("services.market.nikkei225_valuation_service", "nikkei225_valuation_service", "get_data"),
    ("services.market.topix_valuation_service", "topix_valuation_service", "get_data"),
    # MOF 対外証券売買 (月水金 08:50 発表 → 16:30でも十分)
    ("services.market.mof_securities_trading_service", "mof_securities_trading_service", "get_data"),
    # 電子部品 (METI月次)
    ("services.market.electronic_components_balance_service", "electronic_components_balance_service", "get_data"),
    # SHFE銅在庫 (上海15:00 CST = 16:00 JST)
    ("services.market.shfe_copper_stock_service", "shfe_copper_stock_service", "get_data"),
]

# ── 週次: EIA原油/ガソリン/留出油 (木曜 00:00 JST = 水曜 10:30 ET 発表後) ──
EIA_WEEKLY_SERVICES = [
    ("services.market.weekly_crude_oil_inventories_service", "weekly_crude_oil_inventories_service", "get_data"),
    ("services.market.crude_oil_net_demand_service", "crude_oil_net_demand_service", "get_data"),
    ("services.market.cushing_inventory_service", "cushing_inventory_service", "get_data"),
    ("services.market.us_gasoline_inventories_refinery_utilization_service", "us_gasoline_inventories_refinery_utilization_service", "get_data"),
    ("services.market.distillate_fuel_inventories_service", "distillate_fuel_inventories_service", "get_data"),
]

# ── 週次: EIA天然ガス貯蔵 (金曜 00:00 JST = 木曜 10:30 ET 発表後) ──
EIA_GAS_SERVICES = [
    ("services.market.us_natural_gas_storage_service", "us_natural_gas_storage_service", "get_data"),
]

# ── 週次: NAAIM (金曜 08:00 JST = 木曜米国発表後) ──
NAAIM_SERVICES = [
    ("services.market.naaim_service", "naaim_service", "get_naaim_data"),
]

# ── 週次: API原油在庫 (水曜 12:00 JST = 火曜 21:30 EST 発表後) ──
API_CRUDE_SERVICES = [
    ("services.market.api_weekly_crude_oil_inventories_service", "api_weekly_crude_oil_inventories_service", "get_data"),
]

# ── 週次: CFTC/Baker Hughes (土曜 06:00 JST = 金曜 15:30 ET 発表後) ──
CFTC_SERVICES = [
    ("services.market.cftc_positioning_service", "cftc_positioning_service", None),  # 特殊処理
    ("services.market.north_america_rig_count_service", "north_america_rig_count_service", "get_data"),
    ("services.market.roni_service", "roni_service", "get_data"),
]

# ── 月次: 月初〜15日 (08:00 JST) — TSMC, LBMA, EIA STEO ──
MONTHLY_EARLY_SERVICES = [
    ("services.market.tsmc_revenue_service", "tsmc_revenue_service", "get_data"),
    ("services.market.lbma_stock_service", "lbma_stock_service", "get_data"),
    ("services.market.short_term_energy_outlook_service", "short_term_energy_outlook_service", "get_data"),
    ("services.market.steo_natural_gas_service", "steo_natural_gas_service", "get_data"),
    ("services.market.us_shale_oil_production_service", "us_shale_oil_production_service", "get_data"),
]

# ── 月次: 10〜22日 (08:00 JST) — OPEC, IEA ──
MONTHLY_MID_SERVICES = [
    ("services.market.opec_momr_service", "opec_momr_service", "get_data"),
    ("services.market.iea_oil_market_report_service", "iea_oil_market_report_service", "get_data"),
]

# ── 月次: 20〜28日 (08:00 JST) — Eurostat, EIA monthly ──
MONTHLY_LATE_SERVICES = [
    ("services.market.eu_natural_gas_production_service", "eu_natural_gas_production_service", "get_data"),
    ("services.market.us_natural_gas_trade_service", "us_natural_gas_trade_service", "get_data"),
    ("services.market.lng_exports_by_region_service", "lng_exports_by_region_service", "get_data"),
]


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _import_service(module_path: str, singleton_name: str):
    """サービスをインポート（backend prefix のフォールバック付き）
    シングルトンインスタンスを返す。クラスの場合はインスタンス化する。"""
    try:
        mod = __import__(module_path, fromlist=[singleton_name])
    except ImportError:
        mod = __import__(f"backend.{module_path}", fromlist=[singleton_name])
    obj = getattr(mod, singleton_name)
    # クラスの場合はインスタンス化
    if isinstance(obj, type):
        obj = obj()
    return obj


def _refresh_service(module_path: str, singleton_name: str, method_name: str) -> bool:
    """1サービスを force_refresh で呼び出す。成功=True"""
    try:
        svc = _import_service(module_path, singleton_name)
        fn = getattr(svc, method_name)
        result = fn(force_refresh=True)
        # 結果がエラーでないか確認
        if isinstance(result, dict) and result.get("source") == "error":
            logger.warning(f"[MarketScheduler] {singleton_name}: returned error source")
            return False
        return True
    except Exception as e:
        logger.warning(f"[MarketScheduler] {singleton_name}.{method_name} failed: {e}")
        return False


def _refresh_cftc():
    """CFTC Positioning: DisAgg/TFF/Legacy 全銘柄の最新週データをDB追記 → 全25銘柄のキャッシュを再構築"""
    try:
        svc = _import_service(
            "services.market.cftc_positioning_service",
            "cftc_positioning_service",
        )
        # CFTC APIから最新週データを取得しDBに追記 (update_all_latestがキャッシュも削除)
        try:
            counts = svc.update_all_latest()
            logger.info(f"[MarketScheduler] CFTC update_all_latest: {counts}")
        except Exception as e:
            logger.warning(f"[MarketScheduler] CFTC update_all_latest failed: {e}")

        # 全25銘柄のキャッシュを再構築 (1週間アクセスが無くても最新データが反映されるように)
        from services.market.cftc_positioning_service import ALL_ASSETS
        for asset in ALL_ASSETS:
            try:
                svc.get_data(asset=asset, force_refresh=True)
            except Exception as e:
                logger.warning(f"[MarketScheduler] CFTC {asset} failed: {e}")
    except Exception as e:
        logger.warning(f"[MarketScheduler] CFTC import failed: {e}")


def _run_batch(services: list, label: str):
    """サービスリストをまとめて実行"""
    ok = 0
    fail = 0
    start = time.time()

    for module_path, singleton_name, method_name in services:
        if method_name is None:
            _refresh_cftc()
            ok += 1
            continue

        if _refresh_service(module_path, singleton_name, method_name):
            ok += 1
        else:
            fail += 1

    elapsed = time.time() - start
    logger.info(
        f"[MarketScheduler] {label} complete: {ok} ok, {fail} fail, "
        f"{elapsed:.1f}s"
    )
    # 起動時キャッチアップ判定用にマーカーを書き込み
    _set_run_marker(label)


# ---------------------------------------------------------------------------
# スケジューラークラス
# ---------------------------------------------------------------------------

class MarketDataScheduler:
    """マーケットデータ スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    # ── 日次ハンドラー ──

    # NOTE: 各ハンドラは AsyncIOScheduler 上でコルーチンとしてイベントループ上で実行される。
    # _run_batch は yfinance/dukascopy/stooq/requests などの同期ブロッキング I/O を行うため、
    # 直接 await せずワーカースレッドへ退避する。これをしないと起動時 catchup が
    # イベントループを占有し、login 等すべてのエンドポイントが応答不能になる。
    async def _run_us_close(self):
        logger.info("[MarketScheduler] US_CLOSE refresh...")
        await asyncio.to_thread(_run_batch, US_CLOSE_SERVICES, "US_CLOSE")

    async def _run_jp_close(self):
        logger.info("[MarketScheduler] JP_CLOSE refresh...")
        await asyncio.to_thread(_run_batch, JP_CLOSE_SERVICES, "JP_CLOSE")

    # ── 週次ハンドラー ──

    async def _run_eia_weekly(self):
        logger.info("[MarketScheduler] EIA_WEEKLY refresh...")
        await asyncio.to_thread(_run_batch, EIA_WEEKLY_SERVICES, "EIA_WEEKLY")

    async def _run_eia_gas(self):
        logger.info("[MarketScheduler] EIA_GAS refresh...")
        await asyncio.to_thread(_run_batch, EIA_GAS_SERVICES, "EIA_GAS")

    async def _run_naaim(self):
        logger.info("[MarketScheduler] NAAIM refresh...")
        await asyncio.to_thread(_run_batch, NAAIM_SERVICES, "NAAIM")

    async def _run_api_crude(self):
        logger.info("[MarketScheduler] API_CRUDE refresh...")
        await asyncio.to_thread(_run_batch, API_CRUDE_SERVICES, "API_CRUDE")

    async def _run_cftc(self):
        logger.info("[MarketScheduler] CFTC refresh...")
        await asyncio.to_thread(_run_batch, CFTC_SERVICES, "CFTC")

    # ── 月次ハンドラー ──

    async def _run_monthly_early(self):
        logger.info("[MarketScheduler] MONTHLY_EARLY refresh...")
        await asyncio.to_thread(_run_batch, MONTHLY_EARLY_SERVICES, "MONTHLY_EARLY")

    async def _run_monthly_mid(self):
        logger.info("[MarketScheduler] MONTHLY_MID refresh...")
        await asyncio.to_thread(_run_batch, MONTHLY_MID_SERVICES, "MONTHLY_MID")

    async def _run_monthly_late(self):
        logger.info("[MarketScheduler] MONTHLY_LATE refresh...")
        await asyncio.to_thread(_run_batch, MONTHLY_LATE_SERVICES, "MONTHLY_LATE")

    # ── 起動 / 停止 ──

    def start(self):
        """スケジューラーを開始"""

        # ── 日次: US クローズ後 (07:00 + 09:00 JST 平日) ──
        self.scheduler.add_job(
            self._run_us_close,
            CronTrigger(hour=7, minute=0, day_of_week="mon-fri", timezone=JST),
            id="mkt_us_close_07", replace_existing=True, misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run_us_close,
            CronTrigger(hour=9, minute=0, day_of_week="mon-fri", timezone=JST),
            id="mkt_us_close_09", replace_existing=True, misfire_grace_time=3600,
        )

        # ── 日次: JP クローズ後 (16:30 + 20:30 JST 平日) ──
        self.scheduler.add_job(
            self._run_jp_close,
            CronTrigger(hour=16, minute=30, day_of_week="mon-fri", timezone=JST),
            id="mkt_jp_close_16", replace_existing=True, misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run_jp_close,
            CronTrigger(hour=20, minute=30, day_of_week="mon-fri", timezone=JST),
            id="mkt_jp_close_20", replace_existing=True, misfire_grace_time=3600,
        )

        # ── 週次: EIA原油等 (木曜 00:00 JST = 水曜 10:30 ET 発表後) ──
        self.scheduler.add_job(
            self._run_eia_weekly,
            CronTrigger(day_of_week="thu", hour=0, minute=0, timezone=JST),
            id="mkt_eia_weekly", replace_existing=True, misfire_grace_time=3600,
        )

        # ── 週次: EIA天然ガス貯蔵 (金曜 00:00 JST = 木曜 10:30 ET 発表後) ──
        self.scheduler.add_job(
            self._run_eia_gas,
            CronTrigger(day_of_week="fri", hour=0, minute=0, timezone=JST),
            id="mkt_eia_gas", replace_existing=True, misfire_grace_time=3600,
        )

        # ── 週次: NAAIM (金曜 08:00 JST) ──
        self.scheduler.add_job(
            self._run_naaim,
            CronTrigger(day_of_week="fri", hour=8, minute=0, timezone=JST),
            id="mkt_naaim", replace_existing=True, misfire_grace_time=3600,
        )

        # ── 週次: API原油在庫 (水曜 12:00 JST) ──
        self.scheduler.add_job(
            self._run_api_crude,
            CronTrigger(day_of_week="wed", hour=12, minute=0, timezone=JST),
            id="mkt_api_crude", replace_existing=True, misfire_grace_time=3600,
        )

        # ── 週次: CFTC / Baker Hughes (土曜 06:00 JST) ──
        self.scheduler.add_job(
            self._run_cftc,
            CronTrigger(day_of_week="sat", hour=6, minute=0, timezone=JST),
            id="mkt_cftc", replace_existing=True, misfire_grace_time=7200,
        )

        # ── 月次: 月初〜15日 毎日 08:00 (1-15日 平日) ──
        self.scheduler.add_job(
            self._run_monthly_early,
            CronTrigger(day="1-15", hour=8, minute=0, day_of_week="mon-fri", timezone=JST),
            id="mkt_monthly_early", replace_existing=True, misfire_grace_time=3600,
        )

        # ── 月次: 10〜22日 毎日 08:00 (平日) — OPEC/IEA ──
        self.scheduler.add_job(
            self._run_monthly_mid,
            CronTrigger(day="10-22", hour=8, minute=0, day_of_week="mon-fri", timezone=JST),
            id="mkt_monthly_mid", replace_existing=True, misfire_grace_time=3600,
        )

        # ── 月次: 20〜28日 毎日 08:00 (平日) ──
        self.scheduler.add_job(
            self._run_monthly_late,
            CronTrigger(day="20-28", hour=8, minute=0, day_of_week="mon-fri", timezone=JST),
            id="mkt_monthly_late", replace_existing=True, misfire_grace_time=3600,
        )

        # 起動時キャッチアップ:
        # 各バッチの (label, handler, threshold_hours, delay_seconds) を登録。
        # マーカー (前回実行 ts) が threshold_hours を超えていたら 1回 即時実行。
        # delay は他バッチと衝突しないように段階的に増やす。
        catchup_specs = [
            ("US_CLOSE",      self._run_us_close,      24,  30),
            ("JP_CLOSE",      self._run_jp_close,      24,  90),
            ("EIA_WEEKLY",    self._run_eia_weekly,    168, 150),  # 7d
            ("EIA_GAS",       self._run_eia_gas,       168, 210),
            ("NAAIM",         self._run_naaim,         168, 270),
            ("API_CRUDE",     self._run_api_crude,     168, 330),
            ("CFTC",          self._run_cftc,          168, 390),  # 重い (~5min)
            ("MONTHLY_EARLY", self._run_monthly_early, 720, 720),  # 30d
            ("MONTHLY_MID",   self._run_monthly_mid,   720, 780),
            ("MONTHLY_LATE",  self._run_monthly_late,  720, 840),
        ]

        for label, handler, threshold_hours, delay_seconds in catchup_specs:
            age_hours = _get_run_marker_age_hours(label)
            should_catchup = age_hours is None or age_hours >= threshold_hours
            age_str = f"{age_hours:.1f}h" if age_hours is not None else "no marker"
            logger.info(
                f"[MarketScheduler] {label} marker age: {age_str}, "
                f"catchup={should_catchup}"
            )
            if should_catchup:
                self.scheduler.add_job(
                    handler,
                    "date",
                    run_date=datetime.now(JST) + timedelta(seconds=delay_seconds),
                    id=f"mkt_catchup_{label}",
                    replace_existing=True,
                    misfire_grace_time=600,
                )

        self.scheduler.start()

        total = (
            len(US_CLOSE_SERVICES) + len(JP_CLOSE_SERVICES)
            + len(EIA_WEEKLY_SERVICES) + len(EIA_GAS_SERVICES)
            + len(NAAIM_SERVICES) + len(API_CRUDE_SERVICES)
            + len(CFTC_SERVICES)
            + len(MONTHLY_EARLY_SERVICES) + len(MONTHLY_MID_SERVICES)
            + len(MONTHLY_LATE_SERVICES)
        )
        logger.info(
            f"[MarketScheduler] Started — {total} services across 11 schedules"
        )

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


market_data_scheduler = MarketDataScheduler()
