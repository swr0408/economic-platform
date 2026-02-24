"""
Economic Platform API - メインエントリーポイント
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from backend.config import SEASONALITY_DIR, SCREENSHOT_DIR, ALLOWED_ORIGINS
    from backend.routers.seasonality import router as seasonality_router
    from backend.routers.usa.fed_h15 import router as fed_h15_router
    from backend.routers.usa.nyfed import router as nyfed_router
    from backend.routers.usa.fred import router as fred_router
    from backend.routers.usa.frb_total_assets import router as frb_total_assets_router
    from backend.routers.usa.reserve_balances import router as reserve_balances_router
    from backend.routers.usa.tga import router as tga_router
    from backend.routers.usa.oas import router as oas_router
    from backend.routers.usa.cme_fedwatch import router as cme_fedwatch_router
    from backend.routers.usa.fomc_projections import router as fomc_projections_router
    from backend.routers.dashboard import router as dashboard_router
    from backend.routers.market import router as market_router
    from backend.routers.calendar import router as calendar_router
    from backend.routers.market_impact import router as market_impact_router
    from backend.routers.japan.ois_curve import router as japan_ois_curve_router
    from backend.routers.japan.boj_meeting_expectations import router as japan_boj_expectations_router
    from backend.routers.japan.boj_outlook import router as japan_boj_outlook_router
    from backend.routers.japan.quarterly_gdp import router as japan_quarterly_gdp_router
    from backend.routers.japan.gdp_components import router as japan_gdp_components_router
    from backend.routers.japan.gdp_deflator import router as japan_gdp_deflator_router
    from backend.routers.japan.potential_growth import router as japan_potential_growth_router
    from backend.routers.japan.boj_potential_growth import router as japan_boj_potential_growth_router
    from backend.routers.japan.boj_lending import router as japan_boj_lending_router
    from backend.routers.japan.capital_investment import router as japan_capital_investment_router
    from backend.routers.japan.japan_iip import router as japan_iip_router
    from backend.routers.japan.japan_capacity_utilization import router as japan_capacity_utilization_router
    from backend.routers.japan.japan_iip_forecast import router as japan_iip_forecast_router
    from backend.routers.japan.boj_tankan import router as japan_boj_tankan_router
    from backend.routers.japan.bsi import router as japan_bsi_router
    from backend.routers.japan.consumer_sentiment import router as japan_consumer_sentiment_router
    from backend.routers.japan.boj_cai import router as japan_boj_cai_router
    from backend.routers.japan.economy_watcher import router as japan_economy_watcher_router
    from backend.routers.japan.jp_pmi import router as japan_pmi_router
    from backend.routers.japan.retail_sales import router as japan_retail_sales_router
    from backend.routers.japan.scheduled_wage import router as japan_scheduled_wage_router
    from backend.routers.japan.national_cpi import router as japan_national_cpi_router
    from backend.routers.japan.tokyo_cpi import router as japan_tokyo_cpi_router
    from backend.routers.japan.cpi_categories import router as japan_cpi_categories_router
    from backend.routers.japan.sppi import router as japan_sppi_router
    from backend.routers.japan.cgpi import router as japan_cgpi_router
    from backend.routers.japan.cgpi_food_agriculture import router as japan_cgpi_food_agriculture_router
    from backend.routers.japan.import_export_price import router as japan_import_export_price_router
    from backend.routers.japan.pos_uvpi import router as japan_pos_uvpi_router
    from backend.routers.japan.gdp_gap import router as japan_gdp_gap_router
    from backend.routers.japan.boj_gdp_gap import router as japan_boj_gdp_gap_router
    from backend.routers.japan.machinery_orders import router as japan_machinery_orders_router
    from backend.routers.japan.machinery_orders_forecast import router as japan_machinery_orders_forecast_router
    from backend.routers.japan.tertiary_industry_index import router as japan_tertiary_industry_index_router
    from backend.routers.japan.bei import router as japan_bei_router
    from backend.routers.japan.price_di_spread import router as japan_price_di_spread_router
    from backend.routers.eurozone.ecb_rates import router as eurozone_ecb_rates_router
    from backend.routers.eurozone.eurex_ois import router as eurozone_eurex_ois_router
    from backend.routers.eurozone.ecb_rate_cuts_screenshot import router as eurozone_ecb_rate_cuts_screenshot_router
    from backend.routers.eurozone.ecb_macro_projections import router as eurozone_ecb_macro_projections_router
    from backend.routers.eurozone.ecb_gdp import router as eurozone_ecb_gdp_router
    from backend.routers.eurozone.ecb_gdp_components import router as eurozone_ecb_gdp_components_router
    from backend.routers.eurozone.ecb_bls import router as eurozone_ecb_bls_router
    from backend.routers.eurozone.ecb_production import router as eurozone_ecb_production_router
    from backend.routers.eurozone.eurostat_esi import router as eurozone_esi_router
    from backend.routers.eurozone.euro_policy_uncertainty import router as eurozone_policy_uncertainty_router
    from backend.routers.eurozone.ecb_retail_trade import router as eurozone_ecb_retail_trade_router
    from backend.routers.eurozone.eu_pmi import router as eurozone_pmi_router
    from backend.routers.eurozone.ecb_labor_productivity import router as eurozone_labor_productivity_router
    from backend.routers.eurozone.ecb_unit_labour_cost import router as eurozone_unit_labour_cost_router
    from backend.routers.eurozone.eurostat_wages import router as eurozone_eurostat_wages_router
    from backend.routers.eurozone.ecb_negotiated_wages import router as eurozone_ecb_negotiated_wages_router
    from backend.routers.eurozone.indeed_euro_wage import router as eurozone_indeed_euro_wage_router
    from backend.routers.eurozone.germany_unemployment import router as eurozone_germany_unemployment_router
    from backend.routers.eurozone.ecb_hicp import router as eurozone_ecb_hicp_router
    from backend.routers.eurozone.ecb_ppi import router as eurozone_ecb_ppi_router
    from backend.routers.eurozone.ecb_spf import router as eurozone_ecb_spf_router
    from backend.routers.eurozone.ecb_spf_core import router as eurozone_ecb_spf_core_router
    from backend.routers.eurozone.germany_cpi import router as eurozone_germany_cpi_router
    from backend.routers.eurozone.germany_ppi import router as eurozone_germany_ppi_router
    from backend.routers.eurozone.germany_retail_sales import router as eurozone_germany_retail_sales_router
    from backend.routers.eurozone.ecb_inflation_expectations import router as eurozone_ecb_inflation_expectations_router
    from backend.routers.uk.boe_bank_rate import router as uk_boe_bank_rate_router
    from backend.routers.uk.sonia import router as uk_sonia_router
    from backend.routers.uk.boe_ois_curve import router as uk_boe_ois_curve_router
    from backend.routers.uk.boe_market_expectations import router as uk_boe_market_expectations_router
    from backend.routers.uk.boe_cpi_projections import router as uk_boe_cpi_projections_router
    from backend.routers.uk.boe_gdp_forecast import router as uk_boe_gdp_forecast_router
    from backend.routers.uk.boe_unemployment_forecast import router as uk_boe_unemployment_forecast_router
    from backend.routers.uk.boe_inflation_expectations import router as uk_boe_inflation_expectations_router
    from backend.routers.uk.boe_services_inflation import router as uk_boe_services_inflation_router
    from backend.routers.uk.boe_import_prices import router as uk_boe_import_prices_router
    from backend.routers.uk.boe_dmp_survey import router as uk_boe_dmp_survey_router
    from backend.routers.uk.ons_gdp import router as uk_ons_gdp_router
    from backend.routers.uk.ons_gva import router as uk_ons_gva_router
    from backend.routers.uk.brc_commentary import router as uk_brc_commentary_router
    from backend.routers.uk.uk_qt import router as uk_qt_router
    from backend.routers.uk.uk_trade_balance import router as uk_trade_balance_router
    from backend.routers.uk.uk_current_account import router as uk_current_account_router
    from backend.routers.switzerland.snb import router as switzerland_snb_router
    from backend.routers.switzerland.fso import router as switzerland_fso_router
    from backend.routers.switzerland.kof import router as switzerland_kof_router
    from backend.services.usa.fomc_projections_scheduler import fomc_scheduler
    from backend.services.usa.policy_rate_scheduler import policy_rate_scheduler
    from backend.services.calendar.calendar_scheduler import calendar_scheduler
    from backend.scheduler import indicator_scheduler
    from backend.scheduler.fmp_release_scheduler import fmp_release_scheduler
    from backend.scheduler.dashboard_cache_scheduler import dashboard_cache_scheduler
    from backend.scheduler.japan_potential_growth_scheduler import japan_potential_growth_scheduler
    from backend.scheduler.boj_lending_scheduler import boj_lending_scheduler
except ImportError:
    from config import SEASONALITY_DIR, SCREENSHOT_DIR, ALLOWED_ORIGINS
    from routers.seasonality import router as seasonality_router
    from routers.usa.fed_h15 import router as fed_h15_router
    from routers.usa.nyfed import router as nyfed_router
    from routers.usa.fred import router as fred_router
    from routers.usa.frb_total_assets import router as frb_total_assets_router
    from routers.usa.reserve_balances import router as reserve_balances_router
    from routers.usa.tga import router as tga_router
    from routers.usa.oas import router as oas_router
    from routers.usa.cme_fedwatch import router as cme_fedwatch_router
    from routers.usa.fomc_projections import router as fomc_projections_router
    from routers.usa.treasury import router as treasury_router
    from routers.dashboard import router as dashboard_router
    from routers.market import router as market_router
    from routers.calendar import router as calendar_router
    from routers.market_impact import router as market_impact_router
    from routers.japan.ois_curve import router as japan_ois_curve_router
    from routers.japan.boj_meeting_expectations import router as japan_boj_expectations_router
    from routers.japan.boj_outlook import router as japan_boj_outlook_router
    from routers.japan.quarterly_gdp import router as japan_quarterly_gdp_router
    from routers.japan.gdp_components import router as japan_gdp_components_router
    from routers.japan.gdp_deflator import router as japan_gdp_deflator_router
    from routers.japan.potential_growth import router as japan_potential_growth_router
    from routers.japan.boj_potential_growth import router as japan_boj_potential_growth_router
    from routers.japan.boj_lending import router as japan_boj_lending_router
    from routers.japan.capital_investment import router as japan_capital_investment_router
    from routers.japan.japan_iip import router as japan_iip_router
    from routers.japan.japan_capacity_utilization import router as japan_capacity_utilization_router
    from routers.japan.japan_iip_forecast import router as japan_iip_forecast_router
    from routers.japan.boj_tankan import router as japan_boj_tankan_router
    from routers.japan.bsi import router as japan_bsi_router
    from routers.japan.consumer_sentiment import router as japan_consumer_sentiment_router
    from routers.japan.boj_cai import router as japan_boj_cai_router
    from routers.japan.economy_watcher import router as japan_economy_watcher_router
    from routers.japan.jp_pmi import router as japan_pmi_router
    from routers.japan.retail_sales import router as japan_retail_sales_router
    from routers.japan.scheduled_wage import router as japan_scheduled_wage_router
    from routers.japan.national_cpi import router as japan_national_cpi_router
    from routers.japan.tokyo_cpi import router as japan_tokyo_cpi_router
    from routers.japan.cpi_categories import router as japan_cpi_categories_router
    from routers.japan.sppi import router as japan_sppi_router
    from routers.japan.cgpi import router as japan_cgpi_router
    from routers.japan.cgpi_food_agriculture import router as japan_cgpi_food_agriculture_router
    from routers.japan.import_export_price import router as japan_import_export_price_router
    from routers.japan.pos_uvpi import router as japan_pos_uvpi_router
    from routers.japan.gdp_gap import router as japan_gdp_gap_router
    from routers.japan.boj_gdp_gap import router as japan_boj_gdp_gap_router
    from routers.japan.machinery_orders import router as japan_machinery_orders_router
    from routers.japan.machinery_orders_forecast import router as japan_machinery_orders_forecast_router
    from routers.japan.machine_tool_orders import router as japan_machine_tool_orders_router
    from routers.japan.tertiary_industry_index import router as japan_tertiary_industry_index_router
    from routers.japan.bei import router as japan_bei_router
    from routers.japan.japan_balance_sheet import router as japan_balance_sheet_router
    from routers.japan.current_account import router as japan_current_account_router
    from routers.japan.balance_of_trade import router as japan_balance_of_trade_router
    from routers.japan.terms_of_trade import router as japan_terms_of_trade_router
    from routers.japan.price_di_spread import router as japan_price_di_spread_router
    from routers.eurozone.ecb_rates import router as eurozone_ecb_rates_router
    from routers.eurozone.eurex_ois import router as eurozone_eurex_ois_router
    from routers.eurozone.ecb_rate_cuts_screenshot import router as eurozone_ecb_rate_cuts_screenshot_router
    from routers.eurozone.ecb_macro_projections import router as eurozone_ecb_macro_projections_router
    from routers.eurozone.ecb_gdp import router as eurozone_ecb_gdp_router
    from routers.eurozone.ecb_gdp_components import router as eurozone_ecb_gdp_components_router
    from routers.eurozone.ecb_bls import router as eurozone_ecb_bls_router
    from routers.eurozone.ecb_production import router as eurozone_ecb_production_router
    from routers.eurozone.eurostat_esi import router as eurozone_esi_router
    from routers.eurozone.euro_policy_uncertainty import router as eurozone_policy_uncertainty_router
    from routers.eurozone.ecb_retail_trade import router as eurozone_ecb_retail_trade_router
    from routers.eurozone.eu_pmi import router as eurozone_pmi_router
    from routers.eurozone.germany_pmi import router as eurozone_germany_pmi_router
    from routers.eurozone.france_pmi import router as eurozone_france_pmi_router
    from routers.eurozone.ecb_labor_productivity import router as eurozone_labor_productivity_router
    from routers.eurozone.ecb_unit_labour_cost import router as eurozone_unit_labour_cost_router
    from routers.eurozone.eurostat_wages import router as eurozone_eurostat_wages_router
    from routers.eurozone.ecb_negotiated_wages import router as eurozone_ecb_negotiated_wages_router
    from routers.eurozone.indeed_euro_wage import router as eurozone_indeed_euro_wage_router
    from routers.eurozone.germany_unemployment import router as eurozone_germany_unemployment_router
    from routers.eurozone.ecb_hicp import router as eurozone_ecb_hicp_router
    from routers.eurozone.ecb_ppi import router as eurozone_ecb_ppi_router
    from routers.eurozone.ecb_spf import router as eurozone_ecb_spf_router
    from routers.eurozone.ecb_spf_core import router as eurozone_ecb_spf_core_router
    from routers.eurozone.germany_cpi import router as eurozone_germany_cpi_router
    from routers.eurozone.germany_ppi import router as eurozone_germany_ppi_router
    from routers.eurozone.germany_retail_sales import router as eurozone_germany_retail_sales_router
    from routers.eurozone.ecb_inflation_expectations import router as eurozone_ecb_inflation_expectations_router
    from routers.eurozone.ecb_balance_sheet import router as eurozone_ecb_balance_sheet_router
    from routers.eurozone.ecb_ces_wage_expectations import router as eurozone_ecb_ces_wage_expectations_router
    from routers.eurozone.eu_government_debt_to_gdp_ratio import router as eurozone_eu_govt_debt_gdp_router
    from routers.uk.boe_bank_rate import router as uk_boe_bank_rate_router
    from routers.uk.sonia import router as uk_sonia_router
    from routers.uk.boe_mpc_voting import router as uk_boe_mpc_voting_router
    from routers.uk.boe_ois_curve import router as uk_boe_ois_curve_router
    from routers.uk.boe_market_expectations import router as uk_boe_market_expectations_router
    from routers.uk.boe_cpi_projections import router as uk_boe_cpi_projections_router
    from routers.uk.boe_gdp_forecast import router as uk_boe_gdp_forecast_router
    from routers.uk.boe_unemployment_forecast import router as uk_boe_unemployment_forecast_router
    from routers.uk.boe_inflation_expectations import router as uk_boe_inflation_expectations_router
    from routers.uk.boe_services_inflation import router as uk_boe_services_inflation_router
    from routers.uk.boe_import_prices import router as uk_boe_import_prices_router
    from routers.uk.boe_dmp_survey import router as uk_boe_dmp_survey_router
    from routers.uk.ons_gdp import router as uk_ons_gdp_router
    from routers.uk.ons_gva import router as uk_ons_gva_router
    from routers.uk.ons_production import router as uk_ons_production_router
    from routers.uk.brc_commentary import router as uk_brc_commentary_router
    from routers.uk.rics_residential_survey import router as uk_rics_residential_survey_router
    from routers.uk.uk_qt import router as uk_qt_router
    from routers.uk.uk_trade_balance import router as uk_trade_balance_router
    from routers.uk.uk_current_account import router as uk_current_account_router
    from routers.uk.uk_government_debt_to_gdp_ratio import router as uk_government_debt_to_gdp_ratio_router
    from routers.switzerland.snb import router as switzerland_snb_router
    from routers.switzerland.fso import router as switzerland_fso_router
    from routers.switzerland.kof import router as switzerland_kof_router
    from routers.switzerland.seco import router as switzerland_seco_router
    from routers.switzerland.bfs import router as switzerland_bfs_router
    from routers.canada.boc import router as canada_boc_router
    from routers.canada.boc_rate_cuts_screenshot import router as canada_boc_rate_cuts_screenshot_router
    from routers.canada.statcan import router as canada_statcan_router
    from routers.australia.rba import router as australia_rba_router
    from routers.australia.rba_ois_screenshot import router as australia_rba_ois_screenshot_router
    from routers.australia.rba_expectations_screenshot import router as australia_rba_expectations_screenshot_router
    from routers.australia.abs import router as australia_abs_router
    from routers.australia.melbourne_institute import router as australia_melbourne_institute_router
    from routers.australia.nab import router as australia_nab_router
    from routers.australia.abs_employment import router as australia_abs_employment_router
    from routers.australia.abs_consumer import router as australia_abs_consumer_router
    from routers.australia.abs_economy import router as australia_abs_economy_router
    from routers.australia.abs_housing import router as australia_abs_housing_router
    from routers.australia.apra import router as australia_apra_router
    from routers.newzealand.rbnz import router as newzealand_rbnz_router
    from routers.newzealand.stats_nz import router as newzealand_stats_nz_router
    from services.usa.fomc_projections_scheduler import fomc_scheduler
    from services.usa.policy_rate_scheduler import policy_rate_scheduler
    from services.calendar.calendar_scheduler import calendar_scheduler
    from scheduler import indicator_scheduler
    from scheduler.fmp_release_scheduler import fmp_release_scheduler
    from scheduler.dashboard_cache_scheduler import dashboard_cache_scheduler
    from scheduler.japan_potential_growth_scheduler import japan_potential_growth_scheduler
    from scheduler.boj_lending_scheduler import boj_lending_scheduler
    from scheduler.non_fmp_release_scheduler import non_fmp_release_scheduler

app = FastAPI(title="Economic Platform API", version="1.0.0")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静的ファイル配信（シーズナリティ画像）
if SEASONALITY_DIR.exists():
    app.mount(
        "/static/seasonality",
        StaticFiles(directory=str(SEASONALITY_DIR)),
        name="seasonality",
    )

# 静的ファイル配信（スクリーンショット画像）
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/screenshots",
    StaticFiles(directory=str(SCREENSHOT_DIR)),
    name="screenshots",
)

# ルーター登録
app.include_router(seasonality_router)
app.include_router(fed_h15_router)
app.include_router(nyfed_router)
app.include_router(fred_router)
app.include_router(frb_total_assets_router)
app.include_router(reserve_balances_router)
app.include_router(tga_router)
app.include_router(oas_router)
app.include_router(cme_fedwatch_router)
app.include_router(fomc_projections_router)
app.include_router(treasury_router)
app.include_router(dashboard_router)
app.include_router(market_router)
app.include_router(calendar_router)
app.include_router(market_impact_router)
app.include_router(japan_ois_curve_router)
app.include_router(japan_boj_expectations_router)
app.include_router(japan_boj_outlook_router)
app.include_router(japan_quarterly_gdp_router)
app.include_router(japan_gdp_components_router)
app.include_router(japan_gdp_deflator_router)
app.include_router(japan_potential_growth_router)
app.include_router(japan_boj_potential_growth_router)
app.include_router(japan_boj_lending_router)
app.include_router(japan_capital_investment_router)
app.include_router(japan_iip_router)
app.include_router(japan_capacity_utilization_router)
app.include_router(japan_iip_forecast_router)
app.include_router(japan_boj_tankan_router)
app.include_router(japan_bsi_router)
app.include_router(japan_consumer_sentiment_router)
app.include_router(japan_boj_cai_router)
app.include_router(japan_economy_watcher_router)
app.include_router(japan_pmi_router)
app.include_router(japan_retail_sales_router)
app.include_router(japan_scheduled_wage_router)
app.include_router(japan_national_cpi_router)
app.include_router(japan_tokyo_cpi_router)
app.include_router(japan_cpi_categories_router)
app.include_router(japan_sppi_router)
app.include_router(japan_cgpi_router)
app.include_router(japan_cgpi_food_agriculture_router)
app.include_router(japan_import_export_price_router)
app.include_router(japan_pos_uvpi_router)
app.include_router(japan_gdp_gap_router)
app.include_router(japan_boj_gdp_gap_router)
app.include_router(japan_machinery_orders_router)
app.include_router(japan_machinery_orders_forecast_router)
app.include_router(japan_machine_tool_orders_router)
app.include_router(japan_tertiary_industry_index_router)
app.include_router(japan_bei_router)
app.include_router(japan_balance_sheet_router)
app.include_router(japan_current_account_router)
app.include_router(japan_balance_of_trade_router)
app.include_router(japan_terms_of_trade_router)
app.include_router(japan_price_di_spread_router)
app.include_router(eurozone_ecb_rates_router)
app.include_router(eurozone_eurex_ois_router)
app.include_router(eurozone_ecb_rate_cuts_screenshot_router)
app.include_router(eurozone_ecb_macro_projections_router)
app.include_router(eurozone_ecb_gdp_router)
app.include_router(eurozone_ecb_gdp_components_router)
app.include_router(eurozone_ecb_bls_router)
app.include_router(eurozone_ecb_production_router)
app.include_router(eurozone_esi_router)
app.include_router(eurozone_policy_uncertainty_router)
app.include_router(eurozone_ecb_retail_trade_router)
app.include_router(eurozone_pmi_router)
app.include_router(eurozone_germany_pmi_router)
app.include_router(eurozone_france_pmi_router)
app.include_router(eurozone_labor_productivity_router)
app.include_router(eurozone_unit_labour_cost_router)
app.include_router(eurozone_eurostat_wages_router)
app.include_router(eurozone_ecb_negotiated_wages_router)
app.include_router(eurozone_indeed_euro_wage_router)
app.include_router(eurozone_germany_unemployment_router)
app.include_router(eurozone_ecb_hicp_router)
app.include_router(eurozone_ecb_ppi_router)
app.include_router(eurozone_ecb_spf_router)
app.include_router(eurozone_ecb_spf_core_router)
app.include_router(eurozone_germany_cpi_router)
app.include_router(eurozone_germany_ppi_router)
app.include_router(eurozone_germany_retail_sales_router)
app.include_router(eurozone_ecb_inflation_expectations_router)
app.include_router(eurozone_ecb_balance_sheet_router)
app.include_router(eurozone_ecb_ces_wage_expectations_router)
app.include_router(eurozone_eu_govt_debt_gdp_router)

# UK
app.include_router(uk_boe_bank_rate_router)
app.include_router(uk_sonia_router)
app.include_router(uk_boe_mpc_voting_router)
app.include_router(uk_boe_ois_curve_router)
app.include_router(uk_boe_market_expectations_router)
app.include_router(uk_boe_cpi_projections_router)
app.include_router(uk_boe_gdp_forecast_router)
app.include_router(uk_boe_unemployment_forecast_router)
app.include_router(uk_boe_inflation_expectations_router)
app.include_router(uk_boe_services_inflation_router)
app.include_router(uk_boe_import_prices_router)
app.include_router(uk_boe_dmp_survey_router)
app.include_router(uk_ons_gdp_router)
app.include_router(uk_ons_gva_router)
app.include_router(uk_ons_production_router)
app.include_router(uk_brc_commentary_router)
app.include_router(uk_rics_residential_survey_router)
app.include_router(uk_qt_router)
app.include_router(uk_trade_balance_router)
app.include_router(uk_current_account_router)
app.include_router(uk_government_debt_to_gdp_ratio_router)

# Switzerland
app.include_router(switzerland_snb_router)
app.include_router(switzerland_fso_router)
app.include_router(switzerland_kof_router)
app.include_router(switzerland_seco_router)
app.include_router(switzerland_bfs_router)

# Canada
app.include_router(canada_boc_router)
app.include_router(canada_boc_rate_cuts_screenshot_router)
app.include_router(canada_statcan_router)
app.include_router(australia_rba_router)
app.include_router(australia_rba_ois_screenshot_router)
app.include_router(australia_rba_expectations_screenshot_router)
app.include_router(australia_abs_router)
app.include_router(australia_melbourne_institute_router)
app.include_router(australia_nab_router)
app.include_router(australia_abs_employment_router)
app.include_router(australia_abs_consumer_router)
app.include_router(australia_abs_economy_router)
app.include_router(australia_abs_housing_router)
app.include_router(australia_apra_router)

# New Zealand
app.include_router(newzealand_rbnz_router)
app.include_router(newzealand_stats_nz_router)


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "ok", "message": "Server is running"}


@app.get("/api/health")
async def api_health_check():
    """API ヘルスチェックエンドポイント"""
    return {"status": "ok", "message": "API is running"}


@app.get("/api/scheduler/status")
async def scheduler_status():
    """スケジューラーのステータスを取得"""
    try:
        return {
            "status": "ok",
            "indicator_scheduler": indicator_scheduler.get_status()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.on_event("startup")
async def startup_event():
    """起動時の処理"""
    print(f"SEASONALITY_DIR: {SEASONALITY_DIR}")
    print(f"SEASONALITY_DIR exists: {SEASONALITY_DIR.exists()}")

    # FOMC関連スケジューラーを開始
    try:
        fomc_scheduler.start()
        print("FOMC Projections Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start FOMC Projections Scheduler: {e}")

    try:
        policy_rate_scheduler.start()
        print("Policy Rate Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Policy Rate Scheduler: {e}")

    # 経済指標スケジューラーを開始
    try:
        indicator_scheduler.start()
        print("Economic Indicator Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Economic Indicator Scheduler: {e}")

    # 経済カレンダースケジューラーを開始
    try:
        calendar_scheduler.start()
        print("Calendar Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Calendar Scheduler: {e}")

    # FMP発表日ベーススケジューラーを開始
    try:
        fmp_release_scheduler.start()
        print("FMP Release Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start FMP Release Scheduler: {e}")

    # ダッシュボードキャッシュスケジューラーを開始
    try:
        dashboard_cache_scheduler.start()
        print("Dashboard Cache Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Dashboard Cache Scheduler: {e}")

    # 日本潜在成長率スケジューラーを開始
    try:
        japan_potential_growth_scheduler.start()
        print("Japan Potential Growth Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Japan Potential Growth Scheduler: {e}")

    # 日銀貸出動向スケジューラーを開始
    try:
        boj_lending_scheduler.start()
        print("BOJ Lending Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start BOJ Lending Scheduler: {e}")

    # 非FMP指標スケジューラーを開始
    try:
        non_fmp_release_scheduler.start()
        print("Non-FMP Release Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Non-FMP Release Scheduler: {e}")

    # カナダ決済残高キャッシュをバックグラウンドでウォームアップ
    try:
        from services.canada.ca_settlement_balances_service import ca_settlement_balances_service
        ca_settlement_balances_service.warm_cache()
    except Exception as e:
        print(f"Warning: Could not warm Canada Settlement Balances cache: {e}")

    print("=" * 60)
    print("Economic Platform API started")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """シャットダウン時の処理"""
    try:
        fomc_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down FOMC Scheduler: {e}")

    try:
        policy_rate_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down Policy Rate Scheduler: {e}")

    try:
        indicator_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down Indicator Scheduler: {e}")

    try:
        calendar_scheduler.stop()
    except Exception as e:
        print(f"Warning: Error shutting down Calendar Scheduler: {e}")

    try:
        fmp_release_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down FMP Release Scheduler: {e}")

    try:
        dashboard_cache_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down Dashboard Cache Scheduler: {e}")

    try:
        japan_potential_growth_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down Japan Potential Growth Scheduler: {e}")

    try:
        boj_lending_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down BOJ Lending Scheduler: {e}")

    print("Economic Platform API shutdown complete")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('backend.main:app', host='0.0.0.0', port=8000, reload=True)
