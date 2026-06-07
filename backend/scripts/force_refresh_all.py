"""
全マーケットサービス + ダッシュボードを force_refresh で一括更新するスクリプト

Usage (コンテナ内):
  cd /app && python -m scripts.force_refresh_all
"""
import sys
import os
import time
import traceback

# backend ディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _import(module_path, attr_name):
    try:
        mod = __import__(module_path, fromlist=[attr_name])
        return getattr(mod, attr_name)
    except Exception as e:
        print(f"  IMPORT FAIL: {module_path}.{attr_name} — {e}")
        return None


def refresh_service(module_path, singleton_name, method_name, **kwargs):
    svc = _import(module_path, singleton_name)
    if svc is None:
        return False
    try:
        fn = getattr(svc, method_name)
        fn(force_refresh=True, **kwargs)
        return True
    except Exception as e:
        print(f"  ERROR: {singleton_name}.{method_name} — {e}")
        return False


def run_batch(label, services):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    ok = 0
    fail = 0
    start = time.time()

    for item in services:
        if len(item) == 3:
            mod, name, method = item
            print(f"  [{name}] ...", end=" ", flush=True)
            if refresh_service(mod, name, method):
                print("OK")
                ok += 1
            else:
                print("FAIL")
                fail += 1
        elif len(item) == 4:
            mod, name, method, kwargs = item
            print(f"  [{name}] ({kwargs}) ...", end=" ", flush=True)
            if refresh_service(mod, name, method, **kwargs):
                print("OK")
                ok += 1
            else:
                print("FAIL")
                fail += 1

    elapsed = time.time() - start
    print(f"  => {ok} ok, {fail} fail, {elapsed:.1f}s")
    return ok, fail


def main():
    total_ok = 0
    total_fail = 0
    grand_start = time.time()

    # ── マーケット日次 (US) ──
    ok, fail = run_batch("MARKET: US_CLOSE", [
        ("services.market.fear_greed_service", "fear_greed_service", "get_fear_greed_data"),
        ("services.market.gex_dix_service", "gex_dix_service", "get_gex_dix_data"),
        ("services.market.cboe_pcr_service", "cboe_pcr_service", "get_data"),
        ("services.market.vix_futures_curve_service", "vix_futures_curve_service", "get_data"),
        ("services.market.vix_cross_ratio_service", "vix_cross_ratio_service", "get_data"),
        ("services.market.historical_volatility_service", "historical_volatility_service", "get_data"),
        ("services.market.sector_ratio_service", "sector_ratio_service", "get_data"),
        ("services.market.copper_to_gold_ratio_service", "copper_to_gold_ratio_service", "get_data"),
        ("services.market.russell2000_russell1000_service", "russell2000_russell1000_service", "get_data"),
        ("services.market.nt_magnification_service", "nt_magnification_service", "get_data"),
        ("services.market.cmdi_service", "cmdi_service", "get_data"),
        ("services.market.sp500_valuation_service", "sp500_valuation_service", "get_data"),
        ("services.market.nasdaq100_valuation_service", "nasdaq100_valuation_service", "get_data"),
        ("services.market.us_interest_rate_spread_service", "us_interest_rate_spread_service", "get_data"),
        ("services.market.financial_stress_index_service", "financial_stress_index_service", "get_data"),
        ("services.market.lme_copper_stock_service", "lme_copper_stock_service", "get_data"),
        ("services.market.silver_etf_holdings_service", "silver_etf_holdings_service", "get_data"),
        ("services.market.crude_oil_yoy_service", "crude_oil_yoy_service", "get_data"),
        ("services.market.natural_gas_yoy_service", "natural_gas_yoy_service", "get_data"),
        ("services.market.crack_spread_service", "crack_spread_service", "get_data"),
        ("services.market.eu_natural_gas_storage_service", "eu_natural_gas_storage_service", "get_data"),
        ("services.market.noaa_hdd_cdd_service", "noaa_hdd_cdd_service", "get_data"),
        ("services.market.adjustments_service", "adjustments_service", "get_data"),
    ])
    total_ok += ok; total_fail += fail

    # ── マーケット日次 (JP) ──
    ok, fail = run_batch("MARKET: JP_CLOSE", [
        ("services.market.jpx_pcr_service", "jpx_pcr_service", "get_data"),
        ("services.market.advance_decline_ratio_service", "advance_decline_ratio_service", "get_data"),
        ("services.market.nikkei_regression_service", "nikkei_regression_service", "get_data"),
        ("services.market.nikkei_yoy_service", "nikkei_yoy_service", "get_data"),
        ("services.market.nikkei_double_inverse_service", "nikkei_double_inverse_service", "get_data"),
        ("services.market.sq_analysis_service", "sq_analysis_service", "get_data"),
        ("services.market.nikkei225_valuation_service", "nikkei225_valuation_service", "get_data"),
        ("services.market.topix_valuation_service", "topix_valuation_service", "get_data"),
        ("services.market.mof_securities_trading_service", "mof_securities_trading_service", "get_data"),
        ("services.market.electronic_components_balance_service", "electronic_components_balance_service", "get_data"),
        ("services.market.shfe_copper_stock_service", "shfe_copper_stock_service", "get_data"),
    ])
    total_ok += ok; total_fail += fail

    # ── マーケット週次 ──
    ok, fail = run_batch("MARKET: WEEKLY", [
        ("services.market.weekly_crude_oil_inventories_service", "weekly_crude_oil_inventories_service", "get_data"),
        ("services.market.crude_oil_net_demand_service", "crude_oil_net_demand_service", "get_data"),
        ("services.market.cushing_inventory_service", "cushing_inventory_service", "get_data"),
        ("services.market.us_gasoline_inventories_refinery_utilization_service", "us_gasoline_inventories_refinery_utilization_service", "get_data"),
        ("services.market.distillate_fuel_inventories_service", "distillate_fuel_inventories_service", "get_data"),
        ("services.market.us_natural_gas_storage_service", "us_natural_gas_storage_service", "get_data"),
        ("services.market.naaim_service", "naaim_service", "get_naaim_data"),
        ("services.market.api_weekly_crude_oil_inventories_service", "api_weekly_crude_oil_inventories_service", "get_data"),
        ("services.market.north_america_rig_count_service", "north_america_rig_count_service", "get_data"),
        ("services.market.roni_service", "roni_service", "get_data"),
    ])
    total_ok += ok; total_fail += fail

    # ── CFTC (特殊: asset引数) ──
    print(f"\n{'='*60}")
    print(f"  MARKET: CFTC")
    print(f"{'='*60}")
    cftc_svc = _import("services.market.cftc_positioning_service", "cftc_positioning_service")
    if cftc_svc:
        for asset in ["usdjpy", "eurusd", "gbpusd", "audusd", "nzdusd", "eurjpy", "eurgbp", "usd_index"]:
            print(f"  [cftc_positioning_service] {asset} ...", end=" ", flush=True)
            try:
                cftc_svc.get_data(asset=asset, force_refresh=True)
                print("OK")
                total_ok += 1
            except Exception as e:
                print(f"FAIL: {e}")
                total_fail += 1

    # ── マーケット月次 ──
    ok, fail = run_batch("MARKET: MONTHLY", [
        ("services.market.tsmc_revenue_service", "tsmc_revenue_service", "get_data"),
        ("services.market.lbma_stock_service", "lbma_stock_service", "get_data"),
        ("services.market.short_term_energy_outlook_service", "short_term_energy_outlook_service", "get_data"),
        ("services.market.steo_natural_gas_service", "steo_natural_gas_service", "get_data"),
        ("services.market.us_shale_oil_production_service", "us_shale_oil_production_service", "get_data"),
        ("services.market.opec_momr_service", "opec_momr_service", "get_data"),
        ("services.market.iea_oil_market_report_service", "iea_oil_market_report_service", "get_data"),
        ("services.market.eu_natural_gas_production_service", "eu_natural_gas_production_service", "get_data"),
        ("services.market.us_natural_gas_trade_service", "us_natural_gas_trade_service", "get_data"),
        ("services.market.lng_exports_by_region_service", "lng_exports_by_region_service", "get_data"),
    ])
    total_ok += ok; total_fail += fail

    # ── 専用スケジューラー対象 ──
    ok, fail = run_batch("MARKET: DEDICATED SCHEDULER", [
        ("services.market.comex_gold_stock_service", "comex_gold_stock_service", "get_data"),
        ("services.market.comex_silver_stock_service", "comex_silver_stock_service", "get_data"),
        ("services.market.comex_copper_stock_service", "comex_copper_stock_service", "get_data"),
        ("services.market.gold_etf_holdings_service", "gold_etf_holdings_service", "get_data"),
        ("services.market.wgc_gold_etf_service", "wgc_gold_etf_service", "get_data"),
        ("services.market.gold_premium_service", "gold_premium_service", "get_data"),
        ("services.market.sge_gold_service", "sge_gold_service", "get_data"),
        ("services.market.china_gold_etf_balance_service", "china_gold_etf_balance_service", "get_data"),
        ("services.market.nikkei225_options_service", "nikkei225_options_service", "get_data"),
        ("services.market.ny_option_cut_service", "ny_option_cut_service", "get_data"),
        ("services.market.jpx_investor_trading_service", "jpx_investor_trading_service", "get_data"),
    ])
    total_ok += ok; total_fail += fail

    # ── ダッシュボード全52件 ──
    DASHBOARDS = [
        ("usa", "economy"), ("usa", "consumer"), ("usa", "employment"),
        ("usa", "inflation"), ("usa", "housing"), ("usa", "policy"),
        ("japan", "economy"), ("japan", "consumer"), ("japan", "employment"),
        ("japan", "inflation"), ("japan", "policy"),
        ("eurozone", "economy"), ("eurozone", "consumer"), ("eurozone", "employment"),
        ("eurozone", "inflation"), ("eurozone", "policy"),
        ("uk", "economy"), ("uk", "consumer"), ("uk", "employment"),
        ("uk", "inflation"), ("uk", "housing"), ("uk", "policy"),
        ("australia", "economy"), ("australia", "consumer"), ("australia", "employment"),
        ("australia", "inflation"), ("australia", "housing"), ("australia", "policy"),
        ("canada", "economy"), ("canada", "consumer"), ("canada", "employment"),
        ("canada", "inflation"), ("canada", "housing"), ("canada", "policy"),
        ("china", "economy"), ("china", "consumer"), ("china", "employment"),
        ("china", "inflation"), ("china", "housing"), ("china", "policy"),
        ("switzerland", "economy"), ("switzerland", "consumer"), ("switzerland", "employment"),
        ("switzerland", "inflation"), ("switzerland", "housing"), ("switzerland", "policy"),
        ("newzealand", "economy"), ("newzealand", "consumer"), ("newzealand", "employment"),
        ("newzealand", "inflation"), ("newzealand", "policy"),
        ("global", "economy"),
    ]

    print(f"\n{'='*60}")
    print(f"  DASHBOARDS ({len(DASHBOARDS)} loaders)")
    print(f"{'='*60}")

    try:
        from services.dashboard.registry import get_dashboard_loader
    except ImportError:
        from backend.services.dashboard.registry import get_dashboard_loader

    dash_ok = 0
    dash_fail = 0
    dash_start = time.time()

    for country, category in DASHBOARDS:
        print(f"  [{country}/{category}] ...", end=" ", flush=True)
        try:
            loader = get_dashboard_loader(country, category)
            loader.invalidate_cache()
            loader.get_data()
            print("OK")
            dash_ok += 1
        except Exception as e:
            print(f"FAIL: {e}")
            dash_fail += 1

    dash_elapsed = time.time() - dash_start
    print(f"  => {dash_ok} ok, {dash_fail} fail, {dash_elapsed:.1f}s")
    total_ok += dash_ok
    total_fail += dash_fail

    # ── 結果サマリー ──
    grand_elapsed = time.time() - grand_start
    print(f"\n{'='*60}")
    print(f"  TOTAL: {total_ok} ok, {total_fail} fail, {grand_elapsed:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
