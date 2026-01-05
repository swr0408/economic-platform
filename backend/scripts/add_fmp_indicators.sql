-- ============================================================================
-- FMP 経済指標マッピング追加
-- Excel: FMP_Indicators_by_Country_v2.xlsx から生成
-- ============================================================================

-- 既存データを削除して再投入
DELETE FROM indicator_event_mapping;

-- ============================================================================
-- US (アメリカ) - 122 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 金利・金融政策
    ('us_fed_rate', '', 'US', 'irregular', ARRAY['Fed Interest Rate Decision']),
    ('us_interest_rate_projection_1st', '', 'US', 'quarterly', ARRAY['Interest Rate Projection - 1st Yr']),
    ('us_interest_rate_projection_2nd', '', 'US', 'quarterly', ARRAY['Interest Rate Projection - 2nd Yr']),
    ('us_interest_rate_projection_3rd', '', 'US', 'quarterly', ARRAY['Interest Rate Projection - 3rd Yr']),
    ('us_interest_rate_projection_current', '', 'US', 'quarterly', ARRAY['Interest Rate Projection - Current']),
    ('us_interest_rate_projection_longer', '', 'US', 'quarterly', ARRAY['Interest Rate Projection - Longer']),
    ('us_fomc_projections', '', 'US', 'quarterly', ARRAY['FOMC Economic Projections']),
    ('us_monetary_policy_report', '', 'US', 'semiannual', ARRAY['Monetary Policy Report']),

    -- 雇用
    ('us_nonfarm_payrolls', '', 'US', 'monthly', ARRAY['Non Farm Payrolls', 'Nonfarm Payrolls']),
    ('us_nonfarm_payrolls_private', '', 'US', 'monthly', ARRAY['Nonfarm Payrolls Private']),
    ('us_unemployment_rate', '', 'US', 'monthly', ARRAY['Unemployment Rate']),
    ('us_u6_unemployment_rate', '', 'US', 'monthly', ARRAY['U-6 Unemployment Rate']),
    ('us_participation_rate', '', 'US', 'monthly', ARRAY['Participation Rate']),
    ('us_adp_employment', '', 'US', 'monthly', ARRAY['ADP Employment Change']),
    ('us_initial_claims', '', 'US', 'weekly', ARRAY['Initial Jobless Claims']),
    ('us_continuing_claims', '', 'US', 'weekly', ARRAY['Continuing Jobless Claims']),
    ('us_jobless_claims_4wk_avg', '', 'US', 'weekly', ARRAY['Jobless Claims 4-Week Average']),
    ('us_jolts_openings', '', 'US', 'monthly', ARRAY['JOLTs Job Openings']),
    ('us_jolts_quits', '', 'US', 'monthly', ARRAY['JOLTs Job Quits']),
    ('us_challenger_job_cuts', '', 'US', 'monthly', ARRAY['Challenger Job Cuts']),
    ('us_employment_cost_index', '', 'US', 'quarterly', ARRAY['Employment Cost Index QoQ']),
    ('us_nonfarm_productivity', '', 'US', 'quarterly', ARRAY['Nonfarm Productivity QoQ']),
    ('us_unit_labor_costs', '', 'US', 'quarterly', ARRAY['Unit Labour Costs QoQ']),
    ('us_average_hourly_earnings', '', 'US', 'monthly', ARRAY['Average Hourly Earnings', 'Average Hourly Earnings MoM', 'Average Hourly Earnings YoY']),

    -- GDP
    ('us_gdp_growth', '', 'US', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'Gross Domestic Product QoQ']),
    ('us_gdp_price_index', '', 'US', 'quarterly', ARRAY['GDP Price Index QoQ']),
    ('us_gdp_sales', '', 'US', 'quarterly', ARRAY['GDP Sales QoQ']),
    ('us_atlanta_fed_gdpnow', '', 'US', 'weekly', ARRAY['Atlanta Fed GDPNow']),

    -- インフレ・物価
    ('us_cpi', '', 'US', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY']),
    ('us_core_cpi', '', 'US', 'monthly', ARRAY['Core Inflation Rate MoM', 'Core Inflation Rate YoY']),
    ('us_ppi', '', 'US', 'monthly', ARRAY['Producer Price Index', 'Producer Price Index MoM', 'Producer Price Index YoY']),
    ('us_core_ppi', '', 'US', 'monthly', ARRAY['Core PPI MoM', 'Core PPI YoY']),
    ('us_ppi_ex_food_energy_trade', '', 'US', 'monthly', ARRAY['PPI Ex Food, Energy and Trade MoM', 'PPI Ex Food, Energy and Trade YoY']),
    ('us_pce', '', 'US', 'monthly', ARRAY['PCE Price Index MoM', 'PCE Price Index YoY', 'PCE Prices QoQ']),
    ('us_core_pce', '', 'US', 'monthly', ARRAY['Core PCE Price Index MoM', 'Core PCE Price Index YoY', 'Core PCE Prices QoQ']),
    ('us_import_prices', '', 'US', 'monthly', ARRAY['Import Prices MoM', 'Import Prices YoY']),
    ('us_export_prices', '', 'US', 'monthly', ARRAY['Export Prices MoM', 'Export Prices YoY']),
    ('us_inflation_expectations', '', 'US', 'monthly', ARRAY['Inflation Expectations', 'Consumer Inflation Expectation']),

    -- 消費・小売
    ('us_retail_sales', '', 'US', 'monthly', ARRAY['Retail Sales MoM', 'Retail Sales YoY']),
    ('us_retail_sales_ex_autos', '', 'US', 'monthly', ARRAY['Retail Sales Ex Autos MoM']),
    ('us_retail_sales_ex_gas_autos', '', 'US', 'monthly', ARRAY['Retail Sales Ex Gas/Autos MoM']),
    ('retail_control', '', 'US', 'monthly', ARRAY['Retail Sales Ex Gas/Autos MoM', 'Retail Control', 'Retail Sales Control Group MoM']),
    ('us_personal_income', '', 'US', 'monthly', ARRAY['Personal Income MoM']),
    ('us_personal_spending', '', 'US', 'monthly', ARRAY['Personal Spending MoM']),
    ('us_real_consumer_spending', '', 'US', 'monthly', ARRAY['Real Consumer Spending', 'Real Consumer Spending QoQ']),
    ('us_real_earnings', '', 'US', 'monthly', ARRAY['Real Earnings MoM']),

    -- 消費者信頼感
    ('us_cb_consumer_confidence', '', 'US', 'monthly', ARRAY['CB Consumer Confidence']),
    ('us_michigan_sentiment', '', 'US', 'monthly', ARRAY['Michigan Consumer Sentiment']),
    ('us_michigan_expectations', '', 'US', 'monthly', ARRAY['Michigan Consumer Expectations']),
    ('us_michigan_current', '', 'US', 'monthly', ARRAY['Michigan Current Conditions']),
    ('us_michigan_inflation_exp', '', 'US', 'monthly', ARRAY['Michigan Inflation Expectations']),
    ('us_michigan_5y_inflation_exp', '', 'US', 'monthly', ARRAY['Michigan 5 Year Inflation Expectations']),

    -- 製造業・生産
    ('us_ism_manufacturing', '', 'US', 'monthly', ARRAY['ISM Manufacturing PMI']),
    ('us_ism_manufacturing_employment', '', 'US', 'monthly', ARRAY['ISM Manufacturing Employment']),
    ('us_ism_manufacturing_new_orders', '', 'US', 'monthly', ARRAY['ISM Manufacturing New Orders']),
    ('us_ism_manufacturing_prices', '', 'US', 'monthly', ARRAY['ISM Manufacturing Prices']),
    ('us_ism_services', '', 'US', 'monthly', ARRAY['ISM Non-Manufacturing PMI', 'ISM Services PMI']),
    ('us_ism_services_employment', '', 'US', 'monthly', ARRAY['ISM Non-Manufacturing Employment', 'ISM Services Employment']),
    ('us_ism_services_new_orders', '', 'US', 'monthly', ARRAY['ISM Non-Manufacturing New Orders', 'ISM Services New Orders']),
    ('us_ism_services_prices', '', 'US', 'monthly', ARRAY['ISM Non-Manufacturing Prices', 'ISM Services Prices']),
    ('us_ism_services_activity', '', 'US', 'monthly', ARRAY['ISM Non-Manufacturing Business Activity', 'ISM Services Business Activity']),
    ('us_industrial_production', '', 'US', 'monthly', ARRAY['Industrial Production MoM', 'Industrial Production YoY']),
    ('us_manufacturing_production', '', 'US', 'monthly', ARRAY['Manufacturing Production MoM', 'Manufacturing Production YoY']),
    ('us_capacity_utilization', '', 'US', 'monthly', ARRAY['Capacity Utilization']),
    ('us_factory_orders', '', 'US', 'monthly', ARRAY['Factory Orders MoM', 'Factory Orders ex Transportation']),
    ('us_durable_goods', '', 'US', 'monthly', ARRAY['Durable Goods Orders MoM']),
    ('us_durable_goods_ex_defense', '', 'US', 'monthly', ARRAY['Durable Goods Orders Ex Defense MoM', 'Durable Goods Orders ex Defense MoM']),
    ('us_durable_goods_ex_transport', '', 'US', 'monthly', ARRAY['Durable Goods Orders Ex Transp MoM']),

    -- 地域連銀
    ('us_empire_state', '', 'US', 'monthly', ARRAY['NY Empire State Manufacturing Index']),
    ('us_philly_fed', '', 'US', 'monthly', ARRAY['Philadelphia Fed Manufacturing Index']),
    ('us_philly_fed_business', '', 'US', 'monthly', ARRAY['Philly Fed Business Conditions']),
    ('us_philly_fed_capex', '', 'US', 'monthly', ARRAY['Philly Fed CAPEX Index']),
    ('us_philly_fed_employment', '', 'US', 'monthly', ARRAY['Philly Fed Employment']),
    ('us_philly_fed_new_orders', '', 'US', 'monthly', ARRAY['Philly Fed New Orders']),
    ('us_philly_fed_prices', '', 'US', 'monthly', ARRAY['Philly Fed Prices Paid']),
    ('us_nfib', '', 'US', 'monthly', ARRAY['NFIB Business Optimism Index']),

    -- 住宅
    ('us_housing_starts', '', 'US', 'monthly', ARRAY['Housing Starts', 'Housing Starts MoM']),
    ('us_building_permits', '', 'US', 'monthly', ARRAY['Building Permits']),
    ('us_existing_home_sales', '', 'US', 'monthly', ARRAY['Existing Home Sales', 'Existing Home Sales MoM']),
    ('us_new_home_sales', '', 'US', 'monthly', ARRAY['New Home Sales']),
    ('us_pending_home_sales', '', 'US', 'monthly', ARRAY['Pending Home Sales MoM', 'Pending Home Sales YoY']),
    ('us_house_price_index', '', 'US', 'monthly', ARRAY['House Price Index', 'House Price Index MoM', 'House Price Index YoY']),
    ('us_case_shiller', '', 'US', 'monthly', ARRAY['S&P/Case-Shiller Home Price MoM', 'S&P/Case-Shiller Home Price YoY']),
    ('us_nahb', '', 'US', 'monthly', ARRAY['NAHB Housing Market Index']),

    -- PMI
    ('us_sp_composite_pmi', '', 'US', 'monthly', ARRAY['S&P Global Composite PMI']),
    ('us_sp_manufacturing_pmi', '', 'US', 'monthly', ARRAY['S&P Global Manufacturing PMI']),
    ('us_sp_services_pmi', '', 'US', 'monthly', ARRAY['S&P Global Services PMI']),

    -- その他
    ('us_opec_meeting', '', 'US', 'irregular', ARRAY['OPEC Meeting']),
    ('us_opec_report', '', 'US', 'monthly', ARRAY['OPEC Monthly Report'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- JP (日本) - 63 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 金融政策
    ('jp_boj_rate', '', 'JP', 'irregular', ARRAY['BoJ Interest Rate Decision']),
    ('jp_boj_outlook', '', 'JP', 'quarterly', ARRAY['BoJ Quarterly Outlook Report']),
    ('jp_monetary_policy', '', 'JP', 'irregular', ARRAY['Monetary Policy Statement']),

    -- GDP
    ('jp_gdp_growth', '', 'JP', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY']),
    ('jp_gdp_annualized', '', 'JP', 'quarterly', ARRAY['GDP Growth Annualized']),
    ('jp_gdp_price_index', '', 'JP', 'quarterly', ARRAY['GDP Price Index YoY']),
    ('jp_gdp_capex', '', 'JP', 'quarterly', ARRAY['GDP Capital Expenditure QoQ']),
    ('jp_gdp_external', '', 'JP', 'quarterly', ARRAY['GDP External Demand QoQ']),
    ('jp_gdp_consumption', '', 'JP', 'quarterly', ARRAY['GDP Private Consumption QoQ']),
    ('jp_capital_expenditure', '', 'JP', 'quarterly', ARRAY['Capital Expenditure YoY']),

    -- 日銀短観
    ('jp_tankan_large_manufacturing', '', 'JP', 'quarterly', ARRAY['Tankan Large Manufacturers Index']),
    ('jp_tankan_large_manufacturing_outlook', '', 'JP', 'quarterly', ARRAY['Tankan Large Manufacturing Outlook']),
    ('jp_tankan_large_non_manufacturing', '', 'JP', 'quarterly', ARRAY['Tankan Large Non-Manufacturing Index']),
    ('jp_tankan_non_manufacturing_outlook', '', 'JP', 'quarterly', ARRAY['Tankan Non-Manufacturing Outlook']),
    ('jp_tankan_small_manufacturing', '', 'JP', 'quarterly', ARRAY['Tankan Small Manufacturers Index']),
    ('jp_tankan_small_non_manufacturing', '', 'JP', 'quarterly', ARRAY['Tankan Small Non-Manufacturing Index']),
    ('jp_tankan_large_all_capex', '', 'JP', 'quarterly', ARRAY['Tankan Large All Industry Capex']),
    ('jp_tankan_small_all_capex', '', 'JP', 'quarterly', ARRAY['Tankan All Small Industry CAPEX']),
    ('jp_bsi_manufacturing', '', 'JP', 'quarterly', ARRAY['BSI Large Manufacturing QoQ']),
    ('jp_reuters_tankan', '', 'JP', 'monthly', ARRAY['Reuters Tankan Index']),

    -- 雇用
    ('jp_unemployment_rate', '', 'JP', 'monthly', ARRAY['Unemployment Rate']),
    ('jp_job_offers_ratio', '', 'JP', 'monthly', ARRAY['Jobs/applications ratio']),
    ('jp_cash_earnings', '', 'JP', 'monthly', ARRAY['Average Cash Earnings YoY']),

    -- インフレ・物価
    ('jp_cpi', '', 'JP', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY']),
    ('jp_core_cpi', '', 'JP', 'monthly', ARRAY['Core CPI YoY', 'Core Inflation Rate YoY']),
    ('jp_core_core_cpi', '', 'JP', 'monthly', ARRAY['Inflation Rate Ex-Food and Energy YoY']),
    ('jp_ppi', '', 'JP', 'monthly', ARRAY['Producer Price Index MoM', 'Producer Price Index YoY']),

    -- 生産・製造
    ('jp_industrial_production', '', 'JP', 'monthly', ARRAY['Industrial Production MoM', 'Industrial Production YoY']),
    ('jp_capacity_utilization', '', 'JP', 'monthly', ARRAY['Capacity Utilization']),
    ('jp_machinery_orders', '', 'JP', 'monthly', ARRAY['Machinery Orders MoM', 'Machinery Orders YoY']),
    ('jp_machine_tool_orders', '', 'JP', 'monthly', ARRAY['Machine Tool Orders YoY']),
    ('jp_construction_orders', '', 'JP', 'monthly', ARRAY['Construction Orders YoY']),

    -- 消費・小売
    ('jp_retail_sales', '', 'JP', 'monthly', ARRAY['Retail Sales MoM', 'Retail Sales YoY']),
    ('jp_household_spending', '', 'JP', 'monthly', ARRAY['Household Spending MoM', 'Household Spending YoY']),
    ('jp_consumer_confidence', '', 'JP', 'monthly', ARRAY['Consumer Confidence']),

    -- 景気指標
    ('jp_eco_watchers_current', '', 'JP', 'monthly', ARRAY['Eco Watchers Survey Current']),
    ('jp_eco_watchers_outlook', '', 'JP', 'monthly', ARRAY['Eco Watchers Survey Outlook']),
    ('jp_leading_index', '', 'JP', 'monthly', ARRAY['CB Leading Index', 'Leading Economic Index', 'Leading Index MoM']),
    ('jp_coincident_index', '', 'JP', 'monthly', ARRAY['Coincident Index', 'Coincident Indicator MoM']),

    -- 貿易
    ('jp_exports', '', 'JP', 'monthly', ARRAY['Exports YoY']),
    ('jp_imports', '', 'JP', 'monthly', ARRAY['Imports YoY']),

    -- 住宅
    ('jp_housing_starts', '', 'JP', 'monthly', ARRAY['Housing Starts YoY']),

    -- 金融
    ('jp_bank_lending', '', 'JP', 'monthly', ARRAY['Bank Lending YoY']),

    -- PMI
    ('jp_sp_composite_pmi', '', 'JP', 'monthly', ARRAY['S&P Global Composite PMI']),
    ('jp_sp_manufacturing_pmi', '', 'JP', 'monthly', ARRAY['S&P Global Manufacturing PMI']),
    ('jp_sp_services_pmi', '', 'JP', 'monthly', ARRAY['S&P Global Services PMI', 'Services PMI']),
    ('jp_jibun_composite_pmi', '', 'JP', 'monthly', ARRAY['Jibun Bank Composite PMI']),
    ('jp_jibun_manufacturing_pmi', '', 'JP', 'monthly', ARRAY['Jibun Bank Manufacturing PMI']),
    ('jp_jibun_services_pmi', '', 'JP', 'monthly', ARRAY['Jibun Bank Services PMI'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- EU (ユーロ圏) - 46 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 金融政策
    ('eu_ecb_rate', '', 'EU', 'irregular', ARRAY['ECB Interest Rate Decision', 'Interest Rate Decision']),
    ('eu_deposit_rate', '', 'EU', 'irregular', ARRAY['Deposit Facility Rate']),
    ('eu_marginal_lending_rate', '', 'EU', 'irregular', ARRAY['Marginal Lending Rate']),
    ('eu_ecb_lending_survey', '', 'EU', 'quarterly', ARRAY['ECB Bank Lending Survey']),

    -- GDP
    ('eu_gdp_growth', '', 'EU', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY']),

    -- 雇用
    ('eu_unemployment_rate', '', 'EU', 'monthly', ARRAY['Unemployment Rate']),
    ('eu_employment_change', '', 'EU', 'quarterly', ARRAY['Employment Change QoQ', 'Employment Change YoY']),
    ('eu_wage_growth', '', 'EU', 'quarterly', ARRAY['Wage Growth YoY', 'Negotiated Wage Growth']),
    ('eu_labor_cost_index', '', 'EU', 'quarterly', ARRAY['Labour Cost Index YoY']),

    -- インフレ・物価
    ('eu_cpi', '', 'EU', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY']),
    ('eu_core_cpi', '', 'EU', 'monthly', ARRAY['Core Inflation Rate YoY']),
    ('eu_hicp', '', 'EU', 'monthly', ARRAY['HICP MoM', 'HICP YoY']),
    ('eu_ppi', '', 'EU', 'monthly', ARRAY['Producer Price Index MoM', 'Producer Price Index YoY']),
    ('eu_inflation_expectation', '', 'EU', 'monthly', ARRAY['Consumer Inflation Expectation']),

    -- 生産
    ('eu_industrial_production', '', 'EU', 'monthly', ARRAY['Industrial Production MoM', 'Industrial Production YoY']),

    -- 消費・小売
    ('eu_retail_sales', '', 'EU', 'monthly', ARRAY['Retail Sales MoM', 'Retail Sales YoY']),
    ('eu_consumer_confidence', '', 'EU', 'monthly', ARRAY['Consumer Confidence']),

    -- 景況感
    ('eu_economic_sentiment', '', 'EU', 'monthly', ARRAY['Economic Sentiment']),
    ('eu_business_climate', '', 'EU', 'monthly', ARRAY['Business Climate']),
    ('eu_industrial_sentiment', '', 'EU', 'monthly', ARRAY['Industrial Sentiment']),
    ('eu_services_sentiment', '', 'EU', 'monthly', ARRAY['Services Sentiment']),

    -- 金融
    ('eu_loans_companies', '', 'EU', 'monthly', ARRAY['Loans to Companies YoY']),
    ('eu_loans_households', '', 'EU', 'monthly', ARRAY['Loans to Households YoY']),

    -- PMI
    ('eu_hcob_composite_pmi', '', 'EU', 'monthly', ARRAY['HCOB Composite PMI']),
    ('eu_hcob_manufacturing_pmi', '', 'EU', 'monthly', ARRAY['HCOB Manufacturing PMI', 'Manufacturing PMI']),
    ('eu_hcob_services_pmi', '', 'EU', 'monthly', ARRAY['HCOB Services PMI', 'Services PMI']),
    ('eu_hcob_construction_pmi', '', 'EU', 'monthly', ARRAY['HCOB Construction PMI']),
    ('eu_pmi', '', 'EU', 'monthly', ARRAY['PMI']),

    -- 欧州委員会予測
    ('eu_commission_forecasts', '', 'EU', 'quarterly', ARRAY['European Commission Forecasts']),
    ('eu_commission_spring', '', 'EU', 'annual', ARRAY['European Commission Spring Forecasts']),
    ('eu_commission_autumn', '', 'EU', 'annual', ARRAY['European Commission Autumn Forecasts']),
    ('eu_commission_winter', '', 'EU', 'annual', ARRAY['European Commission Winter Forecasts'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- DE (ドイツ) - 34 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- GDP
    ('de_gdp_growth', '', 'DE', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY']),
    ('de_gdp_full_year_2024', '', 'DE', 'annual', ARRAY['Full Year GDP Growth (2024)']),
    ('de_gdp_full_year_2025', '', 'DE', 'annual', ARRAY['Full Year GDP Growth (2025)']),

    -- 雇用
    ('de_unemployment_rate', '', 'DE', 'monthly', ARRAY['Unemployment Rate']),
    ('de_employment_change', '', 'DE', 'monthly', ARRAY['Employment Change']),

    -- インフレ・物価
    ('de_cpi', '', 'DE', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY']),
    ('de_hicp', '', 'DE', 'monthly', ARRAY['HICP MoM', 'HICP YoY']),
    ('de_ppi', '', 'DE', 'monthly', ARRAY['Producer Price Index MoM', 'Producer Price Index YoY']),
    ('de_import_prices', '', 'DE', 'monthly', ARRAY['Import Prices MoM', 'Import Prices YoY']),

    -- 生産・製造
    ('de_industrial_production', '', 'DE', 'monthly', ARRAY['Industrial Production MoM', 'Industrial Production YoY']),
    ('de_factory_orders', '', 'DE', 'monthly', ARRAY['Factory Orders MoM']),

    -- 消費・小売
    ('de_retail_sales', '', 'DE', 'monthly', ARRAY['Retail Sales MoM', 'Retail Sales YoY']),
    ('de_consumer_confidence', '', 'DE', 'monthly', ARRAY['Consumer Confidence']),

    -- 景況感
    ('de_ifo_business_climate', '', 'DE', 'monthly', ARRAY['Ifo Business Climate']),
    ('de_ifo_current', '', 'DE', 'monthly', ARRAY['Ifo Current Conditions']),
    ('de_ifo_expectations', '', 'DE', 'monthly', ARRAY['Ifo Expectations']),
    ('de_zew_sentiment', '', 'DE', 'monthly', ARRAY['ZEW Economic Sentiment Index']),
    ('de_zew_current', '', 'DE', 'monthly', ARRAY['ZEW Current Conditions']),

    -- PMI
    ('de_hcob_composite_pmi', '', 'DE', 'monthly', ARRAY['HCOB Composite PMI']),
    ('de_hcob_manufacturing_pmi', '', 'DE', 'monthly', ARRAY['HCOB Manufacturing PMI', 'Manufacturing PMI']),
    ('de_hcob_services_pmi', '', 'DE', 'monthly', ARRAY['HCOB Services PMI', 'Services PMI']),
    ('de_pmi', '', 'DE', 'monthly', ARRAY['PMI'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- UK (イギリス) - 63 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 金融政策
    ('uk_boe_rate', '', 'UK', 'irregular', ARRAY['BoE Interest Rate Decision', 'Interest Rate Decision']),
    ('uk_boe_mpc_vote_cut', '', 'UK', 'irregular', ARRAY['BoE MPC Vote Cut']),
    ('uk_boe_mpc_vote_hike', '', 'UK', 'irregular', ARRAY['BoE MPC Vote Hike']),
    ('uk_boe_mpc_vote_unchanged', '', 'UK', 'irregular', ARRAY['BoE MPC Vote Unchanged']),
    ('uk_boe_monetary_policy_report', '', 'UK', 'quarterly', ARRAY['BoE Monetary Policy Report']),
    ('uk_boe_quarterly_bulletin', '', 'UK', 'quarterly', ARRAY['BoE Quarterly Bulletin']),
    ('uk_boe_fpc_minutes', '', 'UK', 'quarterly', ARRAY['BoE FPC Meeting Minutes']),
    ('uk_boe_decision_maker_panel', '', 'UK', 'monthly', ARRAY['BoE Decision Maker Panel']),

    -- GDP
    ('uk_gdp_growth', '', 'UK', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY', 'Gross Domestic Product QoQ']),
    ('uk_gdp_mom', '', 'UK', 'monthly', ARRAY['Gross Domestic Product MoM', 'Gross Domestic Product YoY']),
    ('uk_gdp_3m_avg', '', 'UK', 'monthly', ARRAY['GDP 3-Month Avg']),
    ('uk_business_investment', '', 'UK', 'quarterly', ARRAY['Business Investment QoQ', 'Business Investment YoY']),

    -- 雇用
    ('uk_unemployment_rate', '', 'UK', 'monthly', ARRAY['Unemployment Rate']),
    ('uk_employment_change', '', 'UK', 'monthly', ARRAY['Employment Change']),
    ('uk_claimant_count', '', 'UK', 'monthly', ARRAY['Claimant Count Change']),
    ('uk_average_earnings_ex_bonus', '', 'UK', 'monthly', ARRAY['Average Earnings excl. Bonus', 'Average Earnings excl. Bonus (3Mo/Yr)']),
    ('uk_average_earnings_inc_bonus', '', 'UK', 'monthly', ARRAY['Average Earnings incl. Bonus']),
    ('uk_labor_productivity', '', 'UK', 'quarterly', ARRAY['Labour Productivity QoQ']),

    -- インフレ・物価
    ('uk_cpi', '', 'UK', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY']),
    ('uk_core_cpi', '', 'UK', 'monthly', ARRAY['Core Inflation Rate MoM', 'Core Inflation Rate YoY']),
    ('uk_rpi', '', 'UK', 'monthly', ARRAY['Retail Price Index MoM', 'Retail Price Index YoY']),
    ('uk_core_rpi', '', 'UK', 'monthly', ARRAY['Core RPI MoM', 'Core RPI YoY']),
    ('uk_ppi_input', '', 'UK', 'monthly', ARRAY['PPI Input MoM', 'PPI Input YoY']),
    ('uk_ppi_output', '', 'UK', 'monthly', ARRAY['PPI Output MoM', 'PPI Output YoY']),
    ('uk_ppi_core_output', '', 'UK', 'monthly', ARRAY['PPI Core Output MoM', 'PPI Core Output YoY']),

    -- 生産
    ('uk_industrial_production', '', 'UK', 'monthly', ARRAY['Industrial Production MoM', 'Industrial Production YoY']),
    ('uk_manufacturing_production', '', 'UK', 'monthly', ARRAY['Manufacturing Production MoM', 'Manufacturing Production YoY']),

    -- 消費・小売
    ('uk_retail_sales', '', 'UK', 'monthly', ARRAY['Retail Sales MoM', 'Retail Sales YoY']),
    ('uk_retail_sales_ex_fuel', '', 'UK', 'monthly', ARRAY['Retail Sales Ex Fuel MoM', 'Retail Sales Ex Fuel YoY']),
    ('uk_consumer_confidence', '', 'UK', 'monthly', ARRAY['Consumer Confidence']),
    ('uk_brc_retail_sales', '', 'UK', 'monthly', ARRAY['BRC Retail Sales Monitor YoY']),
    ('uk_brc_shop_price', '', 'UK', 'monthly', ARRAY['BRC Shop Price Index YoY']),
    ('uk_cbi_business_optimism', '', 'UK', 'quarterly', ARRAY['CBI Business Optimism Index']),

    -- 住宅
    ('uk_house_price_index', '', 'UK', 'monthly', ARRAY['House Price Index MoM', 'House Price Index YoY']),
    ('uk_nationwide_house_prices', '', 'UK', 'monthly', ARRAY['Nationwide Housing Prices MoM', 'Nationwide Housing Prices YoY']),
    ('uk_rics_house_price', '', 'UK', 'monthly', ARRAY['RICS House Price Balance']),
    ('uk_mortgage_approvals', '', 'UK', 'monthly', ARRAY['Mortgage Approvals']),
    ('uk_mortgage_lending', '', 'UK', 'monthly', ARRAY['Mortgage Lending']),
    ('uk_bba_mortgage_rate', '', 'UK', 'monthly', ARRAY['BBA Mortgage Rate']),

    -- PMI
    ('uk_sp_composite_pmi', '', 'UK', 'monthly', ARRAY['S&P Global Composite PMI']),
    ('uk_sp_manufacturing_pmi', '', 'UK', 'monthly', ARRAY['S&P Global Manufacturing PMI']),
    ('uk_sp_services_pmi', '', 'UK', 'monthly', ARRAY['S&P Global Services PMI']),
    ('uk_sp_construction_pmi', '', 'UK', 'monthly', ARRAY['S&P Global Construction PMI'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- 投入後の確認
-- ============================================================================
SELECT country, COUNT(*) as count FROM indicator_event_mapping GROUP BY country ORDER BY country;
