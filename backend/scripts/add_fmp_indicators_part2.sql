-- ============================================================================
-- FMP 経済指標マッピング追加 Part 2
-- CA, AU, NZ, CN, CH, FR
-- ============================================================================

-- ============================================================================
-- CA (カナダ) - 39 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 金融政策
    ('ca_boc_rate', '', 'CA', 'irregular', ARRAY['BoC Interest Rate Decision']),

    -- GDP
    ('ca_gdp_growth', '', 'CA', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY']),
    ('ca_gdp_annualized', '', 'CA', 'quarterly', ARRAY['GDP Growth Annualized']),
    ('ca_gdp_mom', '', 'CA', 'monthly', ARRAY['Gross Domestic Product MoM']),
    ('ca_gdp_price_index', '', 'CA', 'quarterly', ARRAY['GDP Implicit Price QoQ']),
    ('ca_labor_productivity', '', 'CA', 'quarterly', ARRAY['Labour Productivity QoQ']),
    ('ca_capacity_utilization', '', 'CA', 'quarterly', ARRAY['Capacity Utilization']),

    -- 雇用
    ('ca_unemployment_rate', '', 'CA', 'monthly', ARRAY['Unemployment Rate']),
    ('ca_employment_change', '', 'CA', 'monthly', ARRAY['Employment Change']),
    ('ca_fulltime_employment', '', 'CA', 'monthly', ARRAY['Full Time Employment Chg']),
    ('ca_parttime_employment', '', 'CA', 'monthly', ARRAY['Part Time Employment Chg']),
    ('ca_participation_rate', '', 'CA', 'monthly', ARRAY['Participation Rate']),
    ('ca_average_hourly_wages', '', 'CA', 'monthly', ARRAY['Average Hourly Wages YoY']),

    -- インフレ・物価
    ('ca_cpi', '', 'CA', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY']),
    ('ca_core_cpi', '', 'CA', 'monthly', ARRAY['Core Inflation Rate MoM', 'Core Inflation Rate YoY']),
    ('ca_ppi', '', 'CA', 'monthly', ARRAY['Producer Price Index MoM', 'Producer Price Index YoY']),
    ('ca_raw_materials', '', 'CA', 'monthly', ARRAY['Raw Materials Prices MoM', 'Raw Materials Prices YoY']),

    -- 消費・小売
    ('ca_retail_sales', '', 'CA', 'monthly', ARRAY['Retail Sales MoM', 'Retail Sales YoY']),
    ('ca_retail_sales_ex_autos', '', 'CA', 'monthly', ARRAY['Retail Sales Ex Autos MoM']),

    -- 製造・生産
    ('ca_manufacturing_sales', '', 'CA', 'monthly', ARRAY['Manufacturing Sales MoM']),

    -- 住宅
    ('ca_housing_starts', '', 'CA', 'monthly', ARRAY['Housing Starts']),
    ('ca_building_permits', '', 'CA', 'monthly', ARRAY['Building Permits']),
    ('ca_new_housing_price', '', 'CA', 'monthly', ARRAY['New Housing Price Index MoM', 'New Housing Price Index YoY']),

    -- 貿易
    ('ca_imports', '', 'CA', 'monthly', ARRAY['Imports']),

    -- PMI
    ('ca_ivey_pmi', '', 'CA', 'monthly', ARRAY['Ivey PMI s.a']),
    ('ca_pmi', '', 'CA', 'monthly', ARRAY['PMI']),
    ('ca_services_pmi', '', 'CA', 'monthly', ARRAY['Services PMI']),
    ('ca_sp_composite_pmi', '', 'CA', 'monthly', ARRAY['S&P Global Composite PMI']),
    ('ca_sp_manufacturing_pmi', '', 'CA', 'monthly', ARRAY['S&P Global Manufacturing PMI']),
    ('ca_sp_services_pmi', '', 'CA', 'monthly', ARRAY['S&P Global Services PMI'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- AU (オーストラリア) - 57 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 金融政策
    ('au_rba_rate', '', 'AU', 'irregular', ARRAY['RBA Interest Rate Decision', 'Interest Rate Decision']),

    -- GDP
    ('au_gdp_growth', '', 'AU', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY']),
    ('au_gdp_capex', '', 'AU', 'quarterly', ARRAY['GDP Capital Expenditure', 'GDP Capital Expenditure QoQ']),
    ('au_gdp_chain_price', '', 'AU', 'quarterly', ARRAY['GDP Chain Price Index QoQ']),
    ('au_gdp_consumption', '', 'AU', 'quarterly', ARRAY['GDP Consumption QoQ', 'GDP Final Consumption QoQ']),
    ('au_capital_expenditure', '', 'AU', 'quarterly', ARRAY['Capital Expenditure MoM', 'Capital Expenditure QoQ']),

    -- 雇用
    ('au_unemployment_rate', '', 'AU', 'monthly', ARRAY['Unemployment Rate']),
    ('au_employment_change', '', 'AU', 'monthly', ARRAY['Employment Change']),
    ('au_fulltime_employment', '', 'AU', 'monthly', ARRAY['Full Time Employment Chg']),
    ('au_parttime_employment', '', 'AU', 'monthly', ARRAY['Part Time Employment Chg']),
    ('au_participation_rate', '', 'AU', 'monthly', ARRAY['Participation Rate']),
    ('au_anz_job_ads', '', 'AU', 'monthly', ARRAY['ANZ Job Advertisements MoM']),
    ('au_wage_price_index', '', 'AU', 'quarterly', ARRAY['Wage Price Index QoQ', 'Wage Price Index YoY']),

    -- インフレ・物価
    ('au_cpi', '', 'AU', 'quarterly', ARRAY['CPI', 'Consumer Price Index', 'Inflation Rate QoQ', 'Inflation Rate YoY']),
    ('au_cpi_monthly', '', 'AU', 'monthly', ARRAY['Monthly CPI Indicator', 'Inflation Rate MoM']),
    ('au_ppi', '', 'AU', 'quarterly', ARRAY['Producer Price Index QoQ', 'Producer Price Index YoY']),
    ('au_rba_trimmed_mean_cpi', '', 'AU', 'quarterly', ARRAY['RBA Trimmed Mean CPI QoQ', 'RBA Trimmed Mean CPI YoY']),
    ('au_rba_weighted_median_cpi', '', 'AU', 'quarterly', ARRAY['RBA Weighted Median CPI QoQ', 'RBA Weighted Median CPI YoY']),
    ('au_inflation_expectations', '', 'AU', 'monthly', ARRAY['Inflation Expectations', 'Consumer Inflation Expectation']),

    -- 消費・小売
    ('au_retail_sales', '', 'AU', 'monthly', ARRAY['Retail Sales MoM', 'Retail Sales QoQ']),
    ('au_household_spending', '', 'AU', 'monthly', ARRAY['Household Spending MoM', 'Household Spending YoY']),

    -- 景況感
    ('au_business_confidence', '', 'AU', 'monthly', ARRAY['Business Confidence']),
    ('au_nab_business_confidence', '', 'AU', 'monthly', ARRAY['NAB Business Confidence']),
    ('au_nab_business_survey', '', 'AU', 'monthly', ARRAY['NAB Business Survey']),
    ('au_business_inventories', '', 'AU', 'quarterly', ARRAY['Business Inventories MoM', 'Business Inventories QoQ']),
    ('au_westpac_consumer_confidence', '', 'AU', 'monthly', ARRAY['Westpac Consumer Confidence Index', 'Westpac Consumer Confidence Change']),
    ('au_westpac_leading', '', 'AU', 'monthly', ARRAY['Westpac Leading Index MoM']),

    -- 住宅
    ('au_building_permits', '', 'AU', 'monthly', ARRAY['Building Permits']),

    -- PMI
    ('au_manufacturing_pmi', '', 'AU', 'monthly', ARRAY['Manufacturing PMI']),
    ('au_services_pmi', '', 'AU', 'monthly', ARRAY['Services PMI']),
    ('au_pmi', '', 'AU', 'monthly', ARRAY['PMI']),
    ('au_judo_composite_pmi', '', 'AU', 'monthly', ARRAY['Judo Bank Composite PMI']),
    ('au_judo_manufacturing_pmi', '', 'AU', 'monthly', ARRAY['Judo Bank Manufacturing PMI']),
    ('au_judo_services_pmi', '', 'AU', 'monthly', ARRAY['Judo Bank Services PMI']),
    ('au_sp_composite_pmi', '', 'AU', 'monthly', ARRAY['S&P Global Composite PMI']),
    ('au_sp_manufacturing_pmi', '', 'AU', 'monthly', ARRAY['S&P Global Manufacturing PMI']),
    ('au_sp_services_pmi', '', 'AU', 'monthly', ARRAY['S&P Global Services PMI'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- NZ (ニュージーランド) - 33 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 金融政策
    ('nz_rbnz_rate', '', 'NZ', 'irregular', ARRAY['RBNZ Interest Rate Decision']),

    -- GDP
    ('nz_gdp_growth', '', 'NZ', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY']),

    -- 雇用
    ('nz_unemployment_rate', '', 'NZ', 'quarterly', ARRAY['Unemployment Rate']),
    ('nz_employment_change', '', 'NZ', 'quarterly', ARRAY['Employment Change QoQ']),
    ('nz_participation_rate', '', 'NZ', 'quarterly', ARRAY['Participation Rate']),
    ('nz_labor_cost_index', '', 'NZ', 'quarterly', ARRAY['Labour Cost Index QoQ', 'Labour Cost Index YoY']),

    -- インフレ・物価
    ('nz_cpi', '', 'NZ', 'quarterly', ARRAY['Consumer Price Index', 'Inflation Rate QoQ', 'Inflation Rate YoY']),
    ('nz_ppi', '', 'NZ', 'quarterly', ARRAY['Producer Price Index QoQ', 'PPI Output QoQ']),
    ('nz_inflation_expectations', '', 'NZ', 'quarterly', ARRAY['Inflation Expectations']),

    -- 消費・小売
    ('nz_retail_sales', '', 'NZ', 'quarterly', ARRAY['Retail Sales QoQ', 'Retail Sales MoM', 'Retail Sales YoY']),

    -- 製造
    ('nz_manufacturing_sales', '', 'NZ', 'quarterly', ARRAY['Manufacturing Sales QoQ', 'Manufacturing Sales YoY']),
    ('nz_capacity_utilization', '', 'NZ', 'quarterly', ARRAY['Capacity Utilization']),

    -- 景況感
    ('nz_business_confidence', '', 'NZ', 'monthly', ARRAY['Business Confidence']),
    ('nz_anz_business_confidence', '', 'NZ', 'monthly', ARRAY['ANZ Business Confidence']),
    ('nz_westpac_consumer_confidence', '', 'NZ', 'quarterly', ARRAY['Westpac Consumer Confidence']),

    -- 貿易
    ('nz_exports', '', 'NZ', 'monthly', ARRAY['Exports']),
    ('nz_export_prices', '', 'NZ', 'quarterly', ARRAY['Export Prices QoQ']),
    ('nz_import_prices', '', 'NZ', 'quarterly', ARRAY['Import Prices QoQ']),
    ('nz_terms_of_trade', '', 'NZ', 'quarterly', ARRAY['Terms of Trade QoQ']),

    -- 住宅
    ('nz_building_permits', '', 'NZ', 'monthly', ARRAY['Building Permits']),

    -- PMI
    ('nz_composite_pmi', '', 'NZ', 'monthly', ARRAY['Composite NZ PCI']),
    ('nz_manufacturing_pmi', '', 'NZ', 'monthly', ARRAY['Business NZ PMI']),
    ('nz_services_pmi', '', 'NZ', 'monthly', ARRAY['Services NZ PSI'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- CN (中国) - 35 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 金融政策
    ('cn_lpr_1y', '', 'CN', 'monthly', ARRAY['Loan Prime Rate 1Y']),
    ('cn_lpr_5y', '', 'CN', 'monthly', ARRAY['Loan Prime Rate 5Y']),

    -- GDP
    ('cn_gdp_growth', '', 'CN', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY']),

    -- 雇用
    ('cn_unemployment_rate', '', 'CN', 'monthly', ARRAY['Unemployment Rate']),

    -- インフレ・物価
    ('cn_cpi', '', 'CN', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY']),
    ('cn_ppi', '', 'CN', 'monthly', ARRAY['Producer Price Index YoY']),

    -- 生産
    ('cn_industrial_production', '', 'CN', 'monthly', ARRAY['Industrial Production YoY']),
    ('cn_industrial_profits', '', 'CN', 'monthly', ARRAY['Industrial Profits YoY']),
    ('cn_capacity_utilization', '', 'CN', 'quarterly', ARRAY['Industrial Capacity Utilization']),

    -- 消費・小売
    ('cn_retail_sales', '', 'CN', 'monthly', ARRAY['Retail Sales YoY']),

    -- 投資
    ('cn_fixed_asset_investment', '', 'CN', 'monthly', ARRAY['Fixed Asset Investment (YTD) YoY']),

    -- 貿易
    ('cn_exports', '', 'CN', 'monthly', ARRAY['Exports', 'Exports YoY']),
    ('cn_imports', '', 'CN', 'monthly', ARRAY['Imports', 'Imports YoY']),

    -- 金融
    ('cn_m2_money_supply', '', 'CN', 'monthly', ARRAY['M2 Money Supply YoY']),
    ('cn_social_financing', '', 'CN', 'monthly', ARRAY['Total Social Financing']),
    ('cn_forex_reserves', '', 'CN', 'monthly', ARRAY['Foreign Exchange Reserves']),

    -- 住宅
    ('cn_house_price_index', '', 'CN', 'monthly', ARRAY['House Price Index YoY']),

    -- 景況感
    ('cn_consumer_confidence', '', 'CN', 'monthly', ARRAY['Thomson Reuters IPSOS PCSI']),

    -- PMI
    ('cn_manufacturing_pmi', '', 'CN', 'monthly', ARRAY['Manufacturing PMI']),
    ('cn_services_pmi', '', 'CN', 'monthly', ARRAY['Services PMI']),
    ('cn_pmi', '', 'CN', 'monthly', ARRAY['PMI']),
    ('cn_nbs_manufacturing_pmi', '', 'CN', 'monthly', ARRAY['NBS Manufacturing PMI']),
    ('cn_nbs_non_manufacturing_pmi', '', 'CN', 'monthly', ARRAY['NBS Non Manufacturing PMI']),
    ('cn_nbs_general_pmi', '', 'CN', 'monthly', ARRAY['NBS General PMI']),
    ('cn_caixin_composite_pmi', '', 'CN', 'monthly', ARRAY['Caixin Composite PMI']),
    ('cn_caixin_manufacturing_pmi', '', 'CN', 'monthly', ARRAY['Caixin Manufacturing PMI']),
    ('cn_caixin_services_pmi', '', 'CN', 'monthly', ARRAY['Caixin Services PMI']),
    ('cn_sp_composite_pmi', '', 'CN', 'monthly', ARRAY['S&P Global Composite PMI'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- CH (スイス) - 22 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 金融政策
    ('ch_snb_rate', '', 'CH', 'irregular', ARRAY['SNB Interest Rate Decision']),

    -- GDP
    ('ch_gdp_growth', '', 'CH', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY']),

    -- 雇用
    ('ch_unemployment_rate', '', 'CH', 'monthly', ARRAY['Unemployment Rate']),
    ('ch_employment_level', '', 'CH', 'quarterly', ARRAY['Employment Level']),
    ('ch_nonfarm_payrolls', '', 'CH', 'quarterly', ARRAY['Non Farm Payrolls']),

    -- インフレ・物価
    ('ch_cpi', '', 'CH', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY']),
    ('ch_ppi', '', 'CH', 'monthly', ARRAY['Producer Price Index MoM', 'Producer Price Index YoY', 'Producer & Import Prices MoM', 'Producer & Import Prices YoY']),

    -- 生産
    ('ch_industrial_production', '', 'CH', 'quarterly', ARRAY['Industrial Production YoY']),

    -- 消費・小売
    ('ch_retail_sales', '', 'CH', 'monthly', ARRAY['Retail Sales MoM', 'Retail Sales YoY']),
    ('ch_consumer_confidence', '', 'CH', 'quarterly', ARRAY['Consumer Confidence']),
    ('ch_seco_consumer_climate', '', 'CH', 'quarterly', ARRAY['SECO Consumer Climate']),

    -- 景況感
    ('ch_kof_leading', '', 'CH', 'monthly', ARRAY['KOF Leading Indicators']),

    -- PMI
    ('ch_manufacturing_pmi', '', 'CH', 'monthly', ARRAY['procure.ch Manufacturing PMI'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- FR (フランス) - 27 indicators
-- ============================================================================
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- GDP
    ('fr_gdp_growth', '', 'FR', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY']),

    -- 雇用
    ('fr_unemployment_rate', '', 'FR', 'quarterly', ARRAY['Unemployment Rate']),
    ('fr_nonfarm_payrolls', '', 'FR', 'quarterly', ARRAY['Non-Farm Payrolls QoQ']),
    ('fr_unemployment_claims', '', 'FR', 'monthly', ARRAY['Unemployment Benefit Claims']),

    -- インフレ・物価
    ('fr_cpi', '', 'FR', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY']),
    ('fr_hicp', '', 'FR', 'monthly', ARRAY['HICP MoM', 'HICP YoY']),
    ('fr_ppi', '', 'FR', 'monthly', ARRAY['Producer Price Index MoM', 'Producer Price Index YoY']),

    -- 生産
    ('fr_industrial_production', '', 'FR', 'monthly', ARRAY['Industrial Production MoM']),

    -- 消費
    ('fr_consumer_confidence', '', 'FR', 'monthly', ARRAY['Consumer Confidence']),
    ('fr_consumer_spending', '', 'FR', 'monthly', ARRAY['Consumer Spending MoM']),
    ('fr_household_consumption', '', 'FR', 'monthly', ARRAY['Household Consumption MoM']),

    -- 景況感
    ('fr_business_confidence', '', 'FR', 'monthly', ARRAY['Business Confidence']),
    ('fr_business_climate', '', 'FR', 'monthly', ARRAY['Business Climate Indicator']),

    -- PMI
    ('fr_manufacturing_pmi', '', 'FR', 'monthly', ARRAY['Manufacturing PMI']),
    ('fr_services_pmi', '', 'FR', 'monthly', ARRAY['Services PMI']),
    ('fr_pmi', '', 'FR', 'monthly', ARRAY['PMI']),
    ('fr_hcob_composite_pmi', '', 'FR', 'monthly', ARRAY['HCOB Composite PMI']),
    ('fr_hcob_manufacturing_pmi', '', 'FR', 'monthly', ARRAY['HCOB Manufacturing PMI']),
    ('fr_hcob_services_pmi', '', 'FR', 'monthly', ARRAY['HCOB Services PMI']),
    ('fr_hcob_construction_pmi', '', 'FR', 'monthly', ARRAY['HCOB Construction PMI'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ============================================================================
-- 投入後の確認
-- ============================================================================
SELECT country, COUNT(*) as count FROM indicator_event_mapping GROUP BY country ORDER BY count DESC;
