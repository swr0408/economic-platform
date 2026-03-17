"""
市場データスケジューラー

=== スケジュール一覧 (すべてJST) ===

■ 毎日 5:00  - NOAA HDD/CDD
■ 毎日 6:00  - yfinance全銘柄日足データ
■ 平日 7:00  - yfinance再試行 / GEX・DIX / 日経YoY / 電子部品受注残 / 日経回帰分析 / クラックスプレッド / VIX期間構造 / HV(実現ボラ) / VIXクロスレシオ
■ 平日 8:00  - CBOE Put/Call Ratio
■ 平日 8:30  - 貴金属(Gold ETF, WGC, Gold Premium, SGE, China Gold ETF, COMEX Gold/Silver/Copper, Silver ETF, LME/SHFE銅)
■ 平日 9:00  - Fear & Greed Index (前日7:10PM ET = JST 9:10) / MOF対外対内証券売買(木金月)
■ 平日 15:30 - 日経YoY(午後) / 日経ダブルインバース
■ 平日 16:00 - 東証プライム騰落レシオ / JPX投資部門別(木曜)
■ 平日 20:30 - JPX Put/Call Ratio
■ 金曜 9:00  - NAAIM Exposure Index (木曜US発表 → 金曜JST朝)
■ 土曜 7:00  - IEA/OPEC次回発表日確認
■ 土曜 8:00  - CFTC建玉報告
■ 土曜 9:00  - EIA原油在庫系(週次5本) / 天然ガス貯蔵 / リグカウント / LBMA在庫
■ 土曜 10:00 - EU天然ガス貯蔵 / RONI / STEO / 天然ガス貿易 / LNG / EU天然ガス生産 / シェールオイル
■ 月初 6:00  - TSMC Revenue (毎月10日)

※ 新しいマーケットサービスを追加した場合は、必ずこのスケジューラーにも登録すること。
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from services.market.yfinance_service_db import yfinance_service_db
except ImportError:
    from backend.services.market.yfinance_service_db import yfinance_service_db


JST = ZoneInfo("Asia/Tokyo")


def _safe_call(name: str, fn):
    """サービス呼び出しのラッパー（例外をキャッチしてログ出力）"""
    try:
        result = fn()
        print(f"[MarketScheduler] {name}: OK")
        return result
    except Exception as e:
        print(f"[MarketScheduler] {name}: ERROR - {e}")
        return None


def _import_service(module_name: str, instance_name: str):
    """サービスのインポート（try/except両パターン対応）"""
    try:
        mod = __import__(f"services.market.{module_name}", fromlist=[instance_name])
    except ImportError:
        mod = __import__(f"backend.services.market.{module_name}", fromlist=[instance_name])
    return getattr(mod, instance_name)


class MarketDataScheduler:
    """市場データの定期更新スケジューラー"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=JST)
        self._is_running = False

    def start(self):
        """スケジューラーを開始"""
        if self._is_running:
            print("[MarketScheduler] Already running")
            return

        # =============================================
        # 毎日 5:00 - NOAA HDD/CDD
        # =============================================
        self.scheduler.add_job(
            self._update_noaa,
            CronTrigger(hour=5, minute=0, timezone=JST),
            id="noaa_hdd_cdd",
            name="NOAA HDD/CDD Daily Update",
            replace_existing=True,
        )

        # =============================================
        # 毎日 6:00 - yfinance全銘柄
        # =============================================
        self.scheduler.add_job(
            self._update_daily_data,
            CronTrigger(hour=6, minute=0, timezone=JST),
            id="market_daily_update",
            name="Market Daily Data Update",
            replace_existing=True,
        )

        # =============================================
        # 平日 7:00 - yfinance再試行 + 日次サービス群①
        # =============================================
        self.scheduler.add_job(
            self._update_daily_data_retry,
            CronTrigger(hour=7, minute=0, day_of_week="mon-fri", timezone=JST),
            id="market_daily_update_retry",
            name="Market Daily Data Update (Retry)",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._update_morning_services,
            CronTrigger(hour=7, minute=10, day_of_week="mon-fri", timezone=JST),
            id="morning_services",
            name="Morning Services (GEX/DIX, Nikkei YoY, Electronic Components, Nikkei Regression)",
            replace_existing=True,
        )

        # =============================================
        # 平日 8:00 - CBOE PCR
        # =============================================
        self.scheduler.add_job(
            self._update_cboe_pcr,
            CronTrigger(hour=8, minute=0, day_of_week="mon-fri", timezone=JST),
            id="cboe_pcr",
            name="CBOE Put/Call Ratio Daily",
            replace_existing=True,
        )

        # =============================================
        # 平日 8:30 - 貴金属・銅 一括更新
        # =============================================
        self.scheduler.add_job(
            self._update_metals,
            CronTrigger(hour=8, minute=30, day_of_week="mon-fri", timezone=JST),
            id="metals_update",
            name="Metals Daily Update (Gold/Silver/Copper ETF & Stocks)",
            replace_existing=True,
        )

        # =============================================
        # 平日 9:00 - Fear & Greed Index
        # =============================================
        self.scheduler.add_job(
            self._update_fear_greed,
            CronTrigger(hour=9, minute=0, day_of_week="mon-fri", timezone=JST),
            id="fear_greed",
            name="Fear & Greed Index Daily",
            replace_existing=True,
        )

        # =============================================
        # 平日 15:30 - 日経YoY(午後) / 日経ダブルインバース
        # =============================================
        self.scheduler.add_job(
            self._update_afternoon_japan,
            CronTrigger(hour=15, minute=45, day_of_week="mon-fri", timezone=JST),
            id="afternoon_japan",
            name="Afternoon Japan (Nikkei YoY PM, Nikkei Double Inverse)",
            replace_existing=True,
        )

        # =============================================
        # 平日 16:00 - 騰落レシオ / JPX投資部門別(木曜)
        # =============================================
        self.scheduler.add_job(
            self._update_afternoon_japan_2,
            CronTrigger(hour=16, minute=0, day_of_week="mon-fri", timezone=JST),
            id="afternoon_japan_2",
            name="Afternoon Japan 2 (Advance/Decline Ratio, JPX Investor Trading)",
            replace_existing=True,
        )

        # =============================================
        # 平日 20:30 - JPX Put/Call Ratio
        # =============================================
        self.scheduler.add_job(
            self._update_jpx_pcr,
            CronTrigger(hour=20, minute=30, day_of_week="mon-fri", timezone=JST),
            id="jpx_pcr",
            name="JPX Put/Call Ratio Daily",
            replace_existing=True,
        )

        # =============================================
        # 金曜 9:00 - NAAIM
        # =============================================
        self.scheduler.add_job(
            self._update_naaim,
            CronTrigger(hour=9, minute=0, day_of_week="fri", timezone=JST),
            id="naaim",
            name="NAAIM Exposure Index (Weekly Friday)",
            replace_existing=True,
        )

        # =============================================
        # 土曜 7:00 - IEA/OPEC次回発表日
        # =============================================
        self.scheduler.add_job(
            self._refresh_report_next_releases,
            CronTrigger(day_of_week="sat", hour=7, minute=0, timezone=JST),
            id="report_next_release_refresh",
            name="IEA/OPEC Next Release Refresh (Saturday)",
            replace_existing=True,
        )

        # =============================================
        # 土曜 8:00 - CFTC建玉報告
        # =============================================
        self.scheduler.add_job(
            self._update_cftc_positioning,
            CronTrigger(day_of_week="sat", hour=8, minute=0, timezone=JST),
            id="cftc_positioning_update",
            name="CFTC Positioning Weekly Update (Saturday)",
            replace_existing=True,
        )

        # =============================================
        # 土曜 9:00 - EIA原油在庫系 + 天然ガス貯蔵 + リグカウント + LBMA
        # =============================================
        self.scheduler.add_job(
            self._update_weekly_energy_1,
            CronTrigger(day_of_week="sat", hour=9, minute=0, timezone=JST),
            id="weekly_energy_1",
            name="Weekly Energy 1 (EIA Crude/Cushing/Distillate/Gasoline, NG Storage, Rig Count, LBMA)",
            replace_existing=True,
        )

        # =============================================
        # 土曜 10:00 - EU天然ガス / RONI / STEO / 天然ガス貿易 / LNG / シェールオイル
        # =============================================
        self.scheduler.add_job(
            self._update_weekly_energy_2,
            CronTrigger(day_of_week="sat", hour=10, minute=0, timezone=JST),
            id="weekly_energy_2",
            name="Weekly Energy 2 (EU NG, RONI, STEO, NG Trade, LNG, Shale Oil)",
            replace_existing=True,
        )

        # =============================================
        # 毎月10日 6:00 - TSMC Revenue
        # =============================================
        self.scheduler.add_job(
            self._update_tsmc_revenue,
            CronTrigger(day=10, hour=6, minute=0, timezone=JST),
            id="tsmc_revenue",
            name="TSMC Revenue Monthly (10th)",
            replace_existing=True,
        )

        # =============================================
        # 毎月1-10日 毎日6:00 - WSTS Semiconductor Sales
        # WSTSの発表日は月初第1週で変動するため、1-10日の間毎日チェック
        # =============================================
        self.scheduler.add_job(
            self._update_semiconductor_sales,
            CronTrigger(day="1-10", hour=6, minute=0, timezone=JST),
            id="semiconductor_sales",
            name="WSTS Semiconductor Sales (1st-10th daily check)",
            replace_existing=True,
        )

        # =============================================
        # 毎月8-14日 毎日6:00 - OECD CLI
        # OECDのCLI発表日は月の10日前後で変動するため、8-14日の間毎日チェック
        # =============================================
        self.scheduler.add_job(
            self._update_oecd_cli,
            CronTrigger(day="8-14", hour=6, minute=0, timezone=JST),
            id="oecd_cli",
            name="OECD CLI Monthly Update (8th-14th daily check)",
            replace_existing=True,
        )

        # =============================================
        # 毎月16-22日 毎日9:00 - 日銀当座預金残高
        # BOJデータ検索サイトは原則8:50頃更新。毎月18-20日頃に前月分公表
        # =============================================
        self.scheduler.add_job(
            self._update_boj_current_account_balance,
            CronTrigger(day="16-22", hour=9, minute=0, timezone=JST),
            id="boj_current_account_balance",
            name="BOJ Current Account Balance Monthly (16th-22nd)",
            replace_existing=True,
        )

        self.scheduler.start()
        self._is_running = True
        print("[MarketScheduler] Started - All jobs scheduled")

    def stop(self):
        """スケジューラーを停止"""
        if not self._is_running:
            return

        self.scheduler.shutdown(wait=False)
        self._is_running = False
        print("[MarketScheduler] Stopped")

    # =========================================================================
    # yfinance (既存)
    # =========================================================================
    def _update_daily_data(self):
        """日足データを更新"""
        print(f"[MarketScheduler] Starting daily update at {datetime.now(JST).isoformat()}")
        try:
            result = yfinance_service_db.update_all_symbols(force_refresh=True)
            print(f"[MarketScheduler] Update completed:")
            print(f"  - Success: {result['success_count']}/{result['total']}")
            print(f"  - Failed: {result['failed_count']}")
            print(f"  - Duration: {result['duration_seconds']:.2f}s")
            if result["errors"]:
                print(f"  - Errors:")
                for err in result["errors"][:5]:
                    print(f"    {err}")
        except Exception as e:
            print(f"[MarketScheduler] Update failed: {e}")
            import traceback
            traceback.print_exc()

    def _update_daily_data_retry(self):
        """失敗した銘柄のみ再試行"""
        print(f"[MarketScheduler] Retry update at {datetime.now(JST).isoformat()}")
        try:
            result = yfinance_service_db.update_all_symbols(force_refresh=False)
            if result["success_count"] > 0:
                print(f"[MarketScheduler] Retry completed: {result['success_count']} updated")
        except Exception as e:
            print(f"[MarketScheduler] Retry failed: {e}")

    # =========================================================================
    # 毎日 5:00 - NOAA
    # =========================================================================
    def _update_noaa(self):
        """NOAA HDD/CDD 日次更新"""
        print(f"[MarketScheduler] NOAA HDD/CDD update at {datetime.now(JST).isoformat()}")
        svc = _import_service("noaa_hdd_cdd_service", "noaa_hdd_cdd_service")
        _safe_call("NOAA HDD/CDD", lambda: svc.get_data(force_refresh=True))

    # =========================================================================
    # 平日 7:10 - 朝の日次サービス群
    # =========================================================================
    def _update_morning_services(self):
        """GEX/DIX, 日経YoY, 電子部品受注残, 日経回帰分析"""
        print(f"[MarketScheduler] Morning services at {datetime.now(JST).isoformat()}")

        svc = _import_service("gex_dix_service", "gex_dix_service")
        _safe_call("GEX/DIX", lambda: svc.get_gex_dix_data(force_refresh=True))

        svc = _import_service("nikkei_yoy_service", "nikkei_yoy_service")
        _safe_call("Nikkei YoY (AM)", lambda: svc.get_data(force_refresh=True))

        svc = _import_service("electronic_components_balance_service", "electronic_components_balance_service")
        _safe_call("Electronic Components", lambda: svc.get_data(force_refresh=True))

        svc = _import_service("nikkei_regression_service", "nikkei_regression_service")
        _safe_call("Nikkei Regression", lambda: svc.get_data(force_refresh=True))

        svc = _import_service("crack_spread_service", "crack_spread_service")
        _safe_call("Crack Spread", lambda: svc.get_data(force_refresh=True))

        svc = _import_service("vix_term_structure_service", "vix_term_structure_service")
        _safe_call("VIX Term Structure", lambda: svc.get_data(force_refresh=True))

        svc = _import_service("historical_volatility_service", "historical_volatility_service")
        _safe_call("Historical Volatility", lambda: svc.get_data(force_refresh=True))

        svc = _import_service("vix_cross_ratio_service", "vix_cross_ratio_service")
        _safe_call("VIX Cross Ratio", lambda: svc.get_data(force_refresh=True))

        svc = _import_service("sector_ratio_service", "sector_ratio_service")
        _safe_call("Sector Ratio", lambda: svc.get_data(force_refresh=True))

    # =========================================================================
    # 平日 8:00 - CBOE PCR
    # =========================================================================
    def _update_cboe_pcr(self):
        """CBOE Put/Call Ratio 日次更新"""
        print(f"[MarketScheduler] CBOE PCR update at {datetime.now(JST).isoformat()}")
        svc = _import_service("cboe_pcr_service", "cboe_pcr_service")
        _safe_call("CBOE PCR", lambda: svc.get_data(force_refresh=True))

    # =========================================================================
    # 平日 8:30 - 貴金属・銅 一括
    # =========================================================================
    def _update_metals(self):
        """貴金属・銅 ETF/在庫 日次一括更新"""
        print(f"[MarketScheduler] Metals update at {datetime.now(JST).isoformat()}")

        services = [
            ("gold_etf_holdings_service", "gold_etf_holdings_service", "Gold ETF Holdings"),
            ("wgc_gold_etf_service", "wgc_gold_etf_service", "WGC Gold ETF"),
            ("gold_premium_service", "gold_premium_service", "Gold Premium"),
            ("sge_gold_service", "sge_gold_service", "SGE Gold"),
            ("china_gold_etf_balance_service", "china_gold_etf_balance_service", "China Gold ETF"),
            ("comex_gold_stock_service", "comex_gold_stock_service", "COMEX Gold Stock"),
            ("comex_silver_stock_service", "comex_silver_stock_service", "COMEX Silver Stock"),
            ("comex_copper_stock_service", "comex_copper_stock_service", "COMEX Copper Stock"),
            ("silver_etf_holdings_service", "silver_etf_holdings_service", "Silver ETF Holdings"),
            ("lme_copper_stock_service", "lme_copper_stock_service", "LME Copper Stock"),
            ("shfe_copper_stock_service", "shfe_copper_stock_service", "SHFE Copper Stock"),
        ]

        for module, instance, label in services:
            svc = _import_service(module, instance)
            _safe_call(label, lambda s=svc: s.get_data(force_refresh=True))

    # =========================================================================
    # 平日 9:00 - Fear & Greed
    # =========================================================================
    def _update_fear_greed(self):
        """Fear & Greed Index / MOF対外対内証券売買 日次更新"""
        print(f"[MarketScheduler] Fear & Greed + MOF update at {datetime.now(JST).isoformat()}")
        svc = _import_service("fear_greed_service", "fear_greed_service")
        _safe_call("Fear & Greed", lambda: svc.get_fear_greed_data(force_refresh=True))

        svc = _import_service("mof_securities_trading_service", "mof_securities_trading_service")
        _safe_call("MOF Securities Trading", lambda: svc.get_data(force_refresh=True))

    # =========================================================================
    # 平日 15:45 - 午後の日本株サービス①
    # =========================================================================
    def _update_afternoon_japan(self):
        """日経YoY(午後) / 日経ダブルインバース"""
        print(f"[MarketScheduler] Afternoon Japan update at {datetime.now(JST).isoformat()}")

        svc = _import_service("nikkei_yoy_service", "nikkei_yoy_service")
        _safe_call("Nikkei YoY (PM)", lambda: svc.get_data(force_refresh=True))

        svc = _import_service("nikkei_double_inverse_service", "nikkei_double_inverse_service")
        _safe_call("Nikkei Double Inverse", lambda: svc.get_data(force_refresh=True))

    # =========================================================================
    # 平日 16:00 - 午後の日本株サービス②
    # =========================================================================
    def _update_afternoon_japan_2(self):
        """騰落レシオ / JPX投資部門別売買"""
        print(f"[MarketScheduler] Afternoon Japan 2 update at {datetime.now(JST).isoformat()}")

        svc = _import_service("advance_decline_ratio_service", "advance_decline_ratio_service")
        _safe_call("Advance/Decline Ratio", lambda: svc.get_data(force_refresh=True))

        svc = _import_service("jpx_investor_trading_service", "jpx_investor_trading_service")
        _safe_call("JPX Investor Trading", lambda: svc.get_data(force_refresh=True))

    # =========================================================================
    # 平日 20:30 - JPX PCR
    # =========================================================================
    def _update_jpx_pcr(self):
        """JPX Put/Call Ratio 日次更新"""
        print(f"[MarketScheduler] JPX PCR update at {datetime.now(JST).isoformat()}")
        svc = _import_service("jpx_pcr_service", "jpx_pcr_service")
        _safe_call("JPX PCR", lambda: svc.get_data(force_refresh=True))

    # =========================================================================
    # 金曜 9:00 - NAAIM
    # =========================================================================
    def _update_naaim(self):
        """NAAIM Exposure Index 週次更新"""
        print(f"[MarketScheduler] NAAIM update at {datetime.now(JST).isoformat()}")
        svc = _import_service("naaim_service", "naaim_service")
        _safe_call("NAAIM", lambda: svc.get_naaim_data(force_refresh=True))

    # =========================================================================
    # 土曜 7:00 - IEA/OPEC次回発表日 (既存)
    # =========================================================================
    def _refresh_report_next_releases(self):
        """IEA/OPEC次回発表日をFMPから確認してRedisキャッシュを更新"""
        print(f"[MarketScheduler] Refreshing IEA/OPEC next release at {datetime.now(JST).isoformat()}")

        try:
            svc = _import_service("iea_oil_market_report_service", "iea_oil_market_report_service")
            result = svc._fetch_and_cache_next_release("market:iea_oil_market_report:next_release")
            print(f"[MarketScheduler] IEA next release: {result.get('date') if result else 'N/A'}")
        except Exception as e:
            print(f"[MarketScheduler] IEA next release refresh error: {e}")

        try:
            svc = _import_service("opec_momr_service", "opec_momr_service")
            result = svc._fetch_and_cache_next_release("market:opec_momr:next_release")
            print(f"[MarketScheduler] OPEC next release: {result.get('date') if result else 'N/A'}")
        except Exception as e:
            print(f"[MarketScheduler] OPEC next release refresh error: {e}")

    # =========================================================================
    # 土曜 8:00 - CFTC (既存)
    # =========================================================================
    def _update_cftc_positioning(self):
        """CFTC建玉報告データを更新（DisAgg + TFF）"""
        print(f"[MarketScheduler] Updating CFTC positioning at {datetime.now(JST).isoformat()}")
        try:
            svc = _import_service("cftc_positioning_service", "cftc_positioning_service")
            result = svc.update_all_latest()
            print(f"[MarketScheduler] CFTC update completed: DisAgg={result['disagg']}, TFF={result['tff']} new rows")
        except Exception as e:
            print(f"[MarketScheduler] CFTC update failed: {e}")
            import traceback
            traceback.print_exc()

    # =========================================================================
    # 土曜 9:00 - 週次エネルギー①
    # =========================================================================
    def _update_weekly_energy_1(self):
        """EIA原油在庫系 + 天然ガス貯蔵 + リグカウント + LBMA"""
        print(f"[MarketScheduler] Weekly Energy 1 at {datetime.now(JST).isoformat()}")

        services = [
            ("weekly_crude_oil_inventories_service", "weekly_crude_oil_inventories_service", "EIA Crude Oil Inventories"),
            ("api_weekly_crude_oil_inventories_service", "api_weekly_crude_oil_inventories_service", "API Crude Oil Inventories"),
            ("cushing_inventory_service", "cushing_inventory_service", "Cushing Inventory"),
            ("distillate_fuel_inventories_service", "distillate_fuel_inventories_service", "Distillate Fuel Inventories"),
            ("us_gasoline_inventories_refinery_utilization_service", "us_gasoline_inventories_refinery_utilization_service", "US Gasoline/Refinery"),
            ("crude_oil_net_demand_service", "crude_oil_net_demand_service", "Crude Oil Net Demand"),
            ("us_natural_gas_storage_service", "us_natural_gas_storage_service", "US NG Storage"),
            ("north_america_rig_count_service", "north_america_rig_count_service", "Rig Count"),
            ("lbma_stock_service", "lbma_stock_service", "LBMA Stock"),
        ]

        for module, instance, label in services:
            svc = _import_service(module, instance)
            _safe_call(label, lambda s=svc: s.get_data(force_refresh=True))

    # =========================================================================
    # 土曜 10:00 - 週次エネルギー②
    # =========================================================================
    def _update_weekly_energy_2(self):
        """EU天然ガス / RONI / STEO / 天然ガス貿易 / LNG / シェールオイル"""
        print(f"[MarketScheduler] Weekly Energy 2 at {datetime.now(JST).isoformat()}")

        services = [
            ("eu_natural_gas_storage_service", "eu_natural_gas_storage_service", "EU NG Storage"),
            ("eu_natural_gas_production_service", "eu_natural_gas_production_service", "EU NG Production"),
            ("roni_service", "roni_service", "RONI"),
            ("short_term_energy_outlook_service", "short_term_energy_outlook_service", "STEO (Crude Oil)"),
            ("steo_natural_gas_service", "steo_natural_gas_service", "STEO (Natural Gas)"),
            ("us_natural_gas_trade_service", "us_natural_gas_trade_service", "US NG Trade"),
            ("lng_exports_by_region_service", "lng_exports_by_region_service", "LNG Exports by Region"),
            ("adjustments_service", "adjustments_service", "Adjustments"),
            ("us_shale_oil_production_service", "us_shale_oil_production_service", "US Shale Oil Production"),
        ]

        for module, instance, label in services:
            svc = _import_service(module, instance)
            _safe_call(label, lambda s=svc: s.get_data(force_refresh=True))

    # =========================================================================
    # 毎月10日 - TSMC Revenue
    # =========================================================================
    def _update_tsmc_revenue(self):
        """TSMC Revenue 月次更新"""
        print(f"[MarketScheduler] TSMC Revenue update at {datetime.now(JST).isoformat()}")
        svc = _import_service("tsmc_revenue_service", "tsmc_revenue_service")
        _safe_call("TSMC Revenue", lambda: svc.get_data(force_refresh=True))

    # =========================================================================
    # 毎月5日 - WSTS Semiconductor Sales
    # =========================================================================
    def _update_semiconductor_sales(self):
        """WSTS 半導体売上高 月次更新（1-10日毎日チェック）"""
        print(f"[MarketScheduler] WSTS Semiconductor Sales check at {datetime.now(JST).isoformat()}")
        try:
            import importlib
            mod = importlib.import_module("services.global.semiconductor_sales_service")
            svc = mod.semiconductor_sales_service
            # URLキャッシュをクリアして最新URLを再検出（月初なので新しいファイルが出ている可能性）
            from core.redis_client import redis_client as _rc
            _rc.delete(svc.URL_CACHE_KEY)
            _safe_call("WSTS Semiconductor Sales", lambda: svc.get_data(force_refresh=True))
        except Exception as e:
            print(f"[MarketScheduler] WSTS Semiconductor Sales error: {e}")

    # =========================================================================
    # 毎月8-14日 - OECD CLI
    # =========================================================================
    def _update_oecd_cli(self):
        """OECD CLI（景気先行指数）月次更新（8-14日毎日チェック）"""
        print(f"[MarketScheduler] OECD CLI check at {datetime.now(JST).isoformat()}")
        try:
            import importlib
            mod = importlib.import_module("services.global.oecd_cli_service")
            svc = mod.oecd_cli_service
            _safe_call("OECD CLI", lambda: svc.get_data(force_refresh=True))
        except Exception as e:
            print(f"[MarketScheduler] OECD CLI error: {e}")

    # =========================================================================
    # 毎月16-22日 - 日銀当座預金残高
    # =========================================================================
    def _update_boj_current_account_balance(self):
        """日銀当座預金残高月次更新（16-22日毎日チェック）"""
        print(f"[MarketScheduler] BOJ Current Account Balance check at {datetime.now(JST).isoformat()}")
        try:
            import importlib
            mod = importlib.import_module("services.japan.boj_current_account_balance_service")
            svc = mod.boj_current_account_balance_service
            _safe_call("BOJ Current Account Balance", lambda: svc.get_data(force_refresh=True))
        except Exception as e:
            print(f"[MarketScheduler] BOJ Current Account Balance error: {e}")

    # =========================================================================
    # 手動実行
    # =========================================================================
    def run_now(self, force_refresh: bool = True):
        """手動で即時実行"""
        print(f"[MarketScheduler] Manual update triggered")
        return yfinance_service_db.update_all_symbols(force_refresh)

    @property
    def is_running(self) -> bool:
        return self._is_running

    def get_next_run_time(self) -> str:
        """次回実行時刻を取得"""
        if not self._is_running:
            return "Not scheduled"

        job = self.scheduler.get_job("market_daily_update")
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return "Unknown"


# シングルトンインスタンス
market_scheduler = MarketDataScheduler()
