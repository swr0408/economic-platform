-- ============================================================================
-- econalpha_name（日本語名）を更新
-- econalpha_idはフロントエンドのoverlayConfig.tsで定義されているIDと一致させる
-- フロントエンドで未実装の指標はeconalpha_idを空文字列にする
-- ============================================================================

-- まずテーブルの制約を変更（econalpha_id を NULL許可に）
ALTER TABLE indicator_event_mapping ALTER COLUMN econalpha_id DROP NOT NULL;
ALTER TABLE indicator_event_mapping ALTER COLUMN econalpha_name DROP NOT NULL;

-- ============================================================================
-- US (アメリカ) - フロントエンドと紐付けあり
-- ============================================================================

-- 景況感（フロントエンド実装済み）
UPDATE indicator_event_mapping SET econalpha_id = 'ism_manufacturing', econalpha_name = 'ISM製造業景況指数' WHERE econalpha_id = 'us_ism_manufacturing';
UPDATE indicator_event_mapping SET econalpha_id = 'ism_non_manufacturing', econalpha_name = 'ISM非製造業景況指数' WHERE econalpha_id = 'us_ism_services';
UPDATE indicator_event_mapping SET econalpha_id = 'empire_state', econalpha_name = 'NY連銀製造業景気指数' WHERE econalpha_id = 'us_empire_state';
UPDATE indicator_event_mapping SET econalpha_id = 'philadelphia_fed', econalpha_name = 'フィラデルフィア連銀製造業景気指数' WHERE econalpha_id = 'us_philly_fed';
UPDATE indicator_event_mapping SET econalpha_id = 'nfib', econalpha_name = 'NFIB中小企業楽観指数' WHERE econalpha_id = 'us_nfib';

-- 生産（フロントエンド実装済み）
UPDATE indicator_event_mapping SET econalpha_id = 'industrial_production', econalpha_name = '鉱工業生産' WHERE econalpha_id = 'us_industrial_production';
UPDATE indicator_event_mapping SET econalpha_id = 'capacity_utilization', econalpha_name = '設備稼働率' WHERE econalpha_id = 'us_capacity_utilization';
UPDATE indicator_event_mapping SET econalpha_id = 'durable_goods', econalpha_name = '耐久財受注' WHERE econalpha_id = 'us_durable_goods';

-- 雇用（フロントエンド実装済み）
UPDATE indicator_event_mapping SET econalpha_id = 'unemployment_rate', econalpha_name = '失業率' WHERE econalpha_id = 'us_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = 'nonfarm_payrolls', econalpha_name = '非農業部門雇用者数' WHERE econalpha_id = 'us_nonfarm_payrolls';
UPDATE indicator_event_mapping SET econalpha_id = 'adp_employment', econalpha_name = 'ADP雇用者数' WHERE econalpha_id = 'us_adp_employment';
UPDATE indicator_event_mapping SET econalpha_id = 'jolts_openings', econalpha_name = 'JOLTS求人件数' WHERE econalpha_id = 'us_jolts_openings';
UPDATE indicator_event_mapping SET econalpha_id = 'labor_force_participation', econalpha_name = '労働参加率' WHERE econalpha_id = 'us_participation_rate';
UPDATE indicator_event_mapping SET econalpha_id = 'initial_claims', econalpha_name = '新規失業保険申請件数' WHERE econalpha_id = 'us_initial_claims';
UPDATE indicator_event_mapping SET econalpha_id = 'continued_claims', econalpha_name = '継続受給者数' WHERE econalpha_id = 'us_continuing_claims';
UPDATE indicator_event_mapping SET econalpha_id = 'challenger_job_cuts', econalpha_name = 'チャレンジャー人員削減' WHERE econalpha_id = 'us_challenger_job_cuts';

-- 賃金（フロントエンド実装済み）
UPDATE indicator_event_mapping SET econalpha_id = 'average_hourly_earnings', econalpha_name = '平均時給' WHERE econalpha_id = 'us_average_hourly_earnings';
UPDATE indicator_event_mapping SET econalpha_id = 'employment_cost_index', econalpha_name = '雇用コスト指数' WHERE econalpha_id = 'us_employment_cost_index';
UPDATE indicator_event_mapping SET econalpha_id = 'unit_labor_cost', econalpha_name = '単位労働コスト' WHERE econalpha_id = 'us_unit_labor_costs';

-- 消費（フロントエンド実装済み）
UPDATE indicator_event_mapping SET econalpha_id = 'retail_sales', econalpha_name = '小売売上高' WHERE econalpha_id = 'us_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = 'cb_consumer_confidence', econalpha_name = 'CB消費者信頼感指数' WHERE econalpha_id = 'us_cb_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = 'michigan_consumer_sentiment', econalpha_name = 'ミシガン大学消費者信頼感指数' WHERE econalpha_id = 'us_michigan_sentiment';
UPDATE indicator_event_mapping SET econalpha_id = 'personal_income', econalpha_name = '個人所得' WHERE econalpha_id = 'us_personal_income';
UPDATE indicator_event_mapping SET econalpha_id = 'pce', econalpha_name = 'PCE（個人消費支出）' WHERE econalpha_id = 'us_pce';

-- ============================================================================
-- US (アメリカ) - フロントエンド未実装（econalpha_idをNULL、名前のみ設定）
-- ============================================================================

-- 金融政策
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'FRB金利決定' WHERE econalpha_id = 'us_fed_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '金利見通し（1年目）' WHERE econalpha_id = 'us_interest_rate_projection_1st';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '金利見通し（2年目）' WHERE econalpha_id = 'us_interest_rate_projection_2nd';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '金利見通し（3年目）' WHERE econalpha_id = 'us_interest_rate_projection_3rd';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '金利見通し（現在）' WHERE econalpha_id = 'us_interest_rate_projection_current';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '金利見通し（長期）' WHERE econalpha_id = 'us_interest_rate_projection_longer';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'FOMC経済予測' WHERE econalpha_id = 'us_fomc_projections';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '金融政策報告書' WHERE econalpha_id = 'us_monetary_policy_report';

-- 雇用（フロントエンド未実装）
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '非農業部門雇用者数（民間）' WHERE econalpha_id = 'us_nonfarm_payrolls_private';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'U-6失業率' WHERE econalpha_id = 'us_u6_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業保険申請件数4週平均' WHERE econalpha_id = 'us_jobless_claims_4wk_avg';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'JOLTS自発的離職者数' WHERE econalpha_id = 'us_jolts_quits';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '非農業部門生産性' WHERE econalpha_id = 'us_nonfarm_productivity';

-- GDP
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'us_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDPデフレーター' WHERE econalpha_id = 'us_gdp_price_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP売上高' WHERE econalpha_id = 'us_gdp_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'アトランタ連銀GDPNow' WHERE econalpha_id = 'us_atlanta_fed_gdpnow';

-- インフレ・物価
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'us_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'コアCPI' WHERE econalpha_id = 'us_core_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者物価指数（PPI）' WHERE econalpha_id = 'us_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'コアPPI' WHERE econalpha_id = 'us_core_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PPI（除く食品・エネルギー・貿易）' WHERE econalpha_id = 'us_ppi_ex_food_energy_trade';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'コアPCE' WHERE econalpha_id = 'us_core_pce';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸入物価' WHERE econalpha_id = 'us_import_prices';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸出物価' WHERE econalpha_id = 'us_export_prices';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'インフレ期待' WHERE econalpha_id = 'us_inflation_expectations';

-- 消費（フロントエンド未実装）
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高（除く自動車）' WHERE econalpha_id = 'us_retail_sales_ex_autos';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高（除くガソリン・自動車）' WHERE econalpha_id = 'us_retail_sales_ex_gas_autos';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '個人支出' WHERE econalpha_id = 'us_personal_spending';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '実質個人消費' WHERE econalpha_id = 'us_real_consumer_spending';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '実質賃金' WHERE econalpha_id = 'us_real_earnings';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ミシガン大学期待指数' WHERE econalpha_id = 'us_michigan_expectations';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ミシガン大学現況指数' WHERE econalpha_id = 'us_michigan_current';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ミシガン大学インフレ期待' WHERE econalpha_id = 'us_michigan_inflation_exp';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ミシガン大学5年インフレ期待' WHERE econalpha_id = 'us_michigan_5y_inflation_exp';

-- 製造業（フロントエンド未実装）
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ISM製造業雇用' WHERE econalpha_id = 'us_ism_manufacturing_employment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ISM製造業新規受注' WHERE econalpha_id = 'us_ism_manufacturing_new_orders';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ISM製造業仕入価格' WHERE econalpha_id = 'us_ism_manufacturing_prices';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ISM非製造業雇用' WHERE econalpha_id = 'us_ism_services_employment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ISM非製造業新規受注' WHERE econalpha_id = 'us_ism_services_new_orders';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ISM非製造業仕入価格' WHERE econalpha_id = 'us_ism_services_prices';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ISM非製造業企業活動' WHERE econalpha_id = 'us_ism_services_activity';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業生産' WHERE econalpha_id = 'us_manufacturing_production';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業受注' WHERE econalpha_id = 'us_factory_orders';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '耐久財受注（除く防衛）' WHERE econalpha_id = 'us_durable_goods_ex_defense';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '耐久財受注（除く輸送機器）' WHERE econalpha_id = 'us_durable_goods_ex_transport';

-- 地域連銀（フロントエンド未実装）
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'フィラデルフィア連銀企業見通し' WHERE econalpha_id = 'us_philly_fed_business';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'フィラデルフィア連銀設備投資' WHERE econalpha_id = 'us_philly_fed_capex';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'フィラデルフィア連銀雇用' WHERE econalpha_id = 'us_philly_fed_employment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'フィラデルフィア連銀新規受注' WHERE econalpha_id = 'us_philly_fed_new_orders';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'フィラデルフィア連銀仕入価格' WHERE econalpha_id = 'us_philly_fed_prices';

-- 住宅
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '住宅着工件数' WHERE econalpha_id = 'us_housing_starts';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '建築許可件数' WHERE econalpha_id = 'us_building_permits';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '中古住宅販売件数' WHERE econalpha_id = 'us_existing_home_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '新築住宅販売件数' WHERE econalpha_id = 'us_new_home_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '中古住宅販売保留件数' WHERE econalpha_id = 'us_pending_home_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '住宅価格指数' WHERE econalpha_id = 'us_house_price_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&P/ケース・シラー住宅価格' WHERE econalpha_id = 'us_case_shiller';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'NAHB住宅市場指数' WHERE econalpha_id = 'us_nahb';

-- PMI
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル総合PMI' WHERE econalpha_id = 'us_sp_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル製造業PMI' WHERE econalpha_id = 'us_sp_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバルサービス業PMI' WHERE econalpha_id = 'us_sp_services_pmi';

-- その他
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'OPEC会合' WHERE econalpha_id = 'us_opec_meeting';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'OPEC月報' WHERE econalpha_id = 'us_opec_report';

-- ============================================================================
-- JP (日本) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀金利決定' WHERE econalpha_id = 'jp_boj_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀四半期展望レポート' WHERE econalpha_id = 'jp_boj_outlook';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '金融政策決定会合' WHERE econalpha_id = 'jp_monetary_policy';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'jp_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP年率換算' WHERE econalpha_id = 'jp_gdp_annualized';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDPデフレーター' WHERE econalpha_id = 'jp_gdp_price_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP設備投資' WHERE econalpha_id = 'jp_gdp_capex';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP外需寄与度' WHERE econalpha_id = 'jp_gdp_external';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP個人消費' WHERE econalpha_id = 'jp_gdp_consumption';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '設備投資' WHERE econalpha_id = 'jp_capital_expenditure';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀短観・大企業製造業' WHERE econalpha_id = 'jp_tankan_large_manufacturing';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀短観・大企業製造業先行き' WHERE econalpha_id = 'jp_tankan_large_manufacturing_outlook';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀短観・大企業非製造業' WHERE econalpha_id = 'jp_tankan_large_non_manufacturing';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀短観・非製造業先行き' WHERE econalpha_id = 'jp_tankan_non_manufacturing_outlook';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀短観・中小企業製造業' WHERE econalpha_id = 'jp_tankan_small_manufacturing';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀短観・中小企業非製造業' WHERE econalpha_id = 'jp_tankan_small_non_manufacturing';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀短観・大企業全産業設備投資' WHERE econalpha_id = 'jp_tankan_large_all_capex';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '日銀短観・中小企業全産業設備投資' WHERE econalpha_id = 'jp_tankan_small_all_capex';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BSI大企業製造業' WHERE econalpha_id = 'jp_bsi_manufacturing';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ロイター短観' WHERE econalpha_id = 'jp_reuters_tankan';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'jp_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '有効求人倍率' WHERE econalpha_id = 'jp_job_offers_ratio';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '現金給与総額' WHERE econalpha_id = 'jp_cash_earnings';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'jp_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'コアCPI' WHERE econalpha_id = 'jp_core_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'コアコアCPI' WHERE econalpha_id = 'jp_core_core_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者物価指数（PPI）' WHERE econalpha_id = 'jp_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '鉱工業生産' WHERE econalpha_id = 'jp_industrial_production';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '設備稼働率' WHERE econalpha_id = 'jp_capacity_utilization';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '機械受注' WHERE econalpha_id = 'jp_machinery_orders';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '工作機械受注' WHERE econalpha_id = 'jp_machine_tool_orders';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '建設受注' WHERE econalpha_id = 'jp_construction_orders';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高' WHERE econalpha_id = 'jp_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '家計支出' WHERE econalpha_id = 'jp_household_spending';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者信頼感' WHERE econalpha_id = 'jp_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '景気ウォッチャー調査・現状判断' WHERE econalpha_id = 'jp_eco_watchers_current';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '景気ウォッチャー調査・先行き判断' WHERE econalpha_id = 'jp_eco_watchers_outlook';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '景気先行指数' WHERE econalpha_id = 'jp_leading_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '景気一致指数' WHERE econalpha_id = 'jp_coincident_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸出' WHERE econalpha_id = 'jp_exports';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸入' WHERE econalpha_id = 'jp_imports';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '住宅着工件数' WHERE econalpha_id = 'jp_housing_starts';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '銀行貸出' WHERE econalpha_id = 'jp_bank_lending';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル総合PMI' WHERE econalpha_id = 'jp_sp_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル製造業PMI' WHERE econalpha_id = 'jp_sp_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバルサービス業PMI' WHERE econalpha_id = 'jp_sp_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'じぶん銀行総合PMI' WHERE econalpha_id = 'jp_jibun_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'じぶん銀行製造業PMI' WHERE econalpha_id = 'jp_jibun_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'じぶん銀行サービス業PMI' WHERE econalpha_id = 'jp_jibun_services_pmi';

-- ============================================================================
-- EU (ユーロ圏) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ECB金利決定' WHERE econalpha_id = 'eu_ecb_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '預金ファシリティ金利' WHERE econalpha_id = 'eu_deposit_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '限界貸出金利' WHERE econalpha_id = 'eu_marginal_lending_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ECB銀行貸出調査' WHERE econalpha_id = 'eu_ecb_lending_survey';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'eu_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'eu_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '雇用者数変化' WHERE econalpha_id = 'eu_employment_change';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '賃金上昇率' WHERE econalpha_id = 'eu_wage_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '労働コスト指数' WHERE econalpha_id = 'eu_labor_cost_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'eu_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'コアCPI' WHERE econalpha_id = 'eu_core_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HICP' WHERE econalpha_id = 'eu_hicp';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者物価指数（PPI）' WHERE econalpha_id = 'eu_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'インフレ期待' WHERE econalpha_id = 'eu_inflation_expectation';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '鉱工業生産' WHERE econalpha_id = 'eu_industrial_production';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高' WHERE econalpha_id = 'eu_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者信頼感' WHERE econalpha_id = 'eu_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '景況感' WHERE econalpha_id = 'eu_economic_sentiment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '企業景況感' WHERE econalpha_id = 'eu_business_climate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '産業景況感' WHERE econalpha_id = 'eu_industrial_sentiment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'サービス業景況感' WHERE econalpha_id = 'eu_services_sentiment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '企業向け貸出' WHERE econalpha_id = 'eu_loans_companies';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '家計向け貸出' WHERE econalpha_id = 'eu_loans_households';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOB総合PMI' WHERE econalpha_id = 'eu_hcob_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOB製造業PMI' WHERE econalpha_id = 'eu_hcob_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOBサービス業PMI' WHERE econalpha_id = 'eu_hcob_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOB建設業PMI' WHERE econalpha_id = 'eu_hcob_construction_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PMI' WHERE econalpha_id = 'eu_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '欧州委員会予測' WHERE econalpha_id = 'eu_commission_forecasts';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '欧州委員会春季予測' WHERE econalpha_id = 'eu_commission_spring';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '欧州委員会秋季予測' WHERE econalpha_id = 'eu_commission_autumn';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '欧州委員会冬季予測' WHERE econalpha_id = 'eu_commission_winter';

-- ============================================================================
-- DE (ドイツ) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'de_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '通年GDP成長率（2024年）' WHERE econalpha_id = 'de_gdp_full_year_2024';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '通年GDP成長率（2025年）' WHERE econalpha_id = 'de_gdp_full_year_2025';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'de_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '雇用者数変化' WHERE econalpha_id = 'de_employment_change';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'de_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HICP' WHERE econalpha_id = 'de_hicp';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者物価指数（PPI）' WHERE econalpha_id = 'de_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸入物価' WHERE econalpha_id = 'de_import_prices';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '鉱工業生産' WHERE econalpha_id = 'de_industrial_production';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業受注' WHERE econalpha_id = 'de_factory_orders';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高' WHERE econalpha_id = 'de_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者信頼感' WHERE econalpha_id = 'de_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'IFO企業景況感' WHERE econalpha_id = 'de_ifo_business_climate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'IFO現況指数' WHERE econalpha_id = 'de_ifo_current';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'IFO期待指数' WHERE econalpha_id = 'de_ifo_expectations';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ZEW景況感' WHERE econalpha_id = 'de_zew_sentiment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ZEW現況指数' WHERE econalpha_id = 'de_zew_current';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOB総合PMI' WHERE econalpha_id = 'de_hcob_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOB製造業PMI' WHERE econalpha_id = 'de_hcob_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOBサービス業PMI' WHERE econalpha_id = 'de_hcob_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PMI' WHERE econalpha_id = 'de_pmi';

-- ============================================================================
-- UK (イギリス) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BOE金利決定' WHERE econalpha_id = 'uk_boe_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BOE MPC利下げ票' WHERE econalpha_id = 'uk_boe_mpc_vote_cut';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BOE MPC利上げ票' WHERE econalpha_id = 'uk_boe_mpc_vote_hike';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BOE MPC据置き票' WHERE econalpha_id = 'uk_boe_mpc_vote_unchanged';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BOE金融政策報告書' WHERE econalpha_id = 'uk_boe_monetary_policy_report';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BOE四半期報告' WHERE econalpha_id = 'uk_boe_quarterly_bulletin';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BOE FPC議事録' WHERE econalpha_id = 'uk_boe_fpc_minutes';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BOE意思決定者パネル' WHERE econalpha_id = 'uk_boe_decision_maker_panel';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率（四半期）' WHERE econalpha_id = 'uk_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率（月次）' WHERE econalpha_id = 'uk_gdp_mom';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP3ヶ月平均' WHERE econalpha_id = 'uk_gdp_3m_avg';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '企業投資' WHERE econalpha_id = 'uk_business_investment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'uk_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '雇用者数変化' WHERE econalpha_id = 'uk_employment_change';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業給付申請件数' WHERE econalpha_id = 'uk_claimant_count';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '平均賃金（除くボーナス）' WHERE econalpha_id = 'uk_average_earnings_ex_bonus';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '平均賃金（含むボーナス）' WHERE econalpha_id = 'uk_average_earnings_inc_bonus';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '労働生産性' WHERE econalpha_id = 'uk_labor_productivity';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'uk_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'コアCPI' WHERE econalpha_id = 'uk_core_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売物価指数（RPI）' WHERE econalpha_id = 'uk_rpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'コアRPI' WHERE econalpha_id = 'uk_core_rpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PPI仕入価格' WHERE econalpha_id = 'uk_ppi_input';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PPI出荷価格' WHERE econalpha_id = 'uk_ppi_output';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PPI出荷価格（コア）' WHERE econalpha_id = 'uk_ppi_core_output';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '鉱工業生産' WHERE econalpha_id = 'uk_industrial_production';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業生産' WHERE econalpha_id = 'uk_manufacturing_production';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高' WHERE econalpha_id = 'uk_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高（除く燃料）' WHERE econalpha_id = 'uk_retail_sales_ex_fuel';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者信頼感' WHERE econalpha_id = 'uk_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BRC小売売上高' WHERE econalpha_id = 'uk_brc_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BRC店舗価格' WHERE econalpha_id = 'uk_brc_shop_price';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'CBI企業楽観指数' WHERE econalpha_id = 'uk_cbi_business_optimism';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '住宅価格指数' WHERE econalpha_id = 'uk_house_price_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ネーションワイド住宅価格' WHERE econalpha_id = 'uk_nationwide_house_prices';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'RICS住宅価格' WHERE econalpha_id = 'uk_rics_house_price';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '住宅ローン承認件数' WHERE econalpha_id = 'uk_mortgage_approvals';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '住宅ローン貸出' WHERE econalpha_id = 'uk_mortgage_lending';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BBA住宅ローン金利' WHERE econalpha_id = 'uk_bba_mortgage_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル総合PMI' WHERE econalpha_id = 'uk_sp_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル製造業PMI' WHERE econalpha_id = 'uk_sp_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバルサービス業PMI' WHERE econalpha_id = 'uk_sp_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル建設業PMI' WHERE econalpha_id = 'uk_sp_construction_pmi';

-- ============================================================================
-- CA (カナダ) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'BOC金利決定' WHERE econalpha_id = 'ca_boc_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'ca_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP年率換算' WHERE econalpha_id = 'ca_gdp_annualized';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP（月次）' WHERE econalpha_id = 'ca_gdp_mom';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDPデフレーター' WHERE econalpha_id = 'ca_gdp_price_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '労働生産性' WHERE econalpha_id = 'ca_labor_productivity';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '設備稼働率' WHERE econalpha_id = 'ca_capacity_utilization';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'ca_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '雇用者数変化' WHERE econalpha_id = 'ca_employment_change';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'フルタイム雇用者数変化' WHERE econalpha_id = 'ca_fulltime_employment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'パートタイム雇用者数変化' WHERE econalpha_id = 'ca_parttime_employment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '労働参加率' WHERE econalpha_id = 'ca_participation_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '平均時給' WHERE econalpha_id = 'ca_average_hourly_wages';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'ca_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'コアCPI' WHERE econalpha_id = 'ca_core_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者物価指数（PPI）' WHERE econalpha_id = 'ca_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '原材料価格' WHERE econalpha_id = 'ca_raw_materials';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高' WHERE econalpha_id = 'ca_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高（除く自動車）' WHERE econalpha_id = 'ca_retail_sales_ex_autos';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業売上高' WHERE econalpha_id = 'ca_manufacturing_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '住宅着工件数' WHERE econalpha_id = 'ca_housing_starts';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '建築許可件数' WHERE econalpha_id = 'ca_building_permits';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '新築住宅価格指数' WHERE econalpha_id = 'ca_new_housing_price';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸入' WHERE econalpha_id = 'ca_imports';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'Ivey PMI' WHERE econalpha_id = 'ca_ivey_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PMI' WHERE econalpha_id = 'ca_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'サービス業PMI' WHERE econalpha_id = 'ca_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル総合PMI' WHERE econalpha_id = 'ca_sp_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル製造業PMI' WHERE econalpha_id = 'ca_sp_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバルサービス業PMI' WHERE econalpha_id = 'ca_sp_services_pmi';

-- ============================================================================
-- AU (オーストラリア) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'RBA金利決定' WHERE econalpha_id = 'au_rba_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'au_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP設備投資' WHERE econalpha_id = 'au_gdp_capex';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDPチェーン価格指数' WHERE econalpha_id = 'au_gdp_chain_price';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP消費' WHERE econalpha_id = 'au_gdp_consumption';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '設備投資' WHERE econalpha_id = 'au_capital_expenditure';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'au_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '雇用者数変化' WHERE econalpha_id = 'au_employment_change';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'フルタイム雇用者数変化' WHERE econalpha_id = 'au_fulltime_employment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'パートタイム雇用者数変化' WHERE econalpha_id = 'au_parttime_employment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '労働参加率' WHERE econalpha_id = 'au_participation_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ANZ求人広告' WHERE econalpha_id = 'au_anz_job_ads';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '賃金価格指数' WHERE econalpha_id = 'au_wage_price_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'au_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '月次CPI' WHERE econalpha_id = 'au_cpi_monthly';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者物価指数（PPI）' WHERE econalpha_id = 'au_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'RBAトリム平均CPI' WHERE econalpha_id = 'au_rba_trimmed_mean_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'RBA加重中央値CPI' WHERE econalpha_id = 'au_rba_weighted_median_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'インフレ期待' WHERE econalpha_id = 'au_inflation_expectations';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高' WHERE econalpha_id = 'au_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '家計支出' WHERE econalpha_id = 'au_household_spending';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '企業信頼感' WHERE econalpha_id = 'au_business_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'NAB企業信頼感' WHERE econalpha_id = 'au_nab_business_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'NAB企業調査' WHERE econalpha_id = 'au_nab_business_survey';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '企業在庫' WHERE econalpha_id = 'au_business_inventories';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ウェストパック消費者信頼感' WHERE econalpha_id = 'au_westpac_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ウェストパック先行指数' WHERE econalpha_id = 'au_westpac_leading';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '建築許可件数' WHERE econalpha_id = 'au_building_permits';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業PMI' WHERE econalpha_id = 'au_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'サービス業PMI' WHERE econalpha_id = 'au_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PMI' WHERE econalpha_id = 'au_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'Judo Bank総合PMI' WHERE econalpha_id = 'au_judo_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'Judo Bank製造業PMI' WHERE econalpha_id = 'au_judo_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'Judo Bankサービス業PMI' WHERE econalpha_id = 'au_judo_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル総合PMI' WHERE econalpha_id = 'au_sp_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル製造業PMI' WHERE econalpha_id = 'au_sp_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバルサービス業PMI' WHERE econalpha_id = 'au_sp_services_pmi';

-- ============================================================================
-- NZ (ニュージーランド) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'RBNZ金利決定' WHERE econalpha_id = 'nz_rbnz_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'nz_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'nz_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '雇用者数変化' WHERE econalpha_id = 'nz_employment_change';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '労働参加率' WHERE econalpha_id = 'nz_participation_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '労働コスト指数' WHERE econalpha_id = 'nz_labor_cost_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'nz_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者物価指数（PPI）' WHERE econalpha_id = 'nz_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'インフレ期待' WHERE econalpha_id = 'nz_inflation_expectations';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高' WHERE econalpha_id = 'nz_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業売上高' WHERE econalpha_id = 'nz_manufacturing_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '設備稼働率' WHERE econalpha_id = 'nz_capacity_utilization';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '企業信頼感' WHERE econalpha_id = 'nz_business_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ANZ企業信頼感' WHERE econalpha_id = 'nz_anz_business_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ウェストパック消費者信頼感' WHERE econalpha_id = 'nz_westpac_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸出' WHERE econalpha_id = 'nz_exports';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸出価格' WHERE econalpha_id = 'nz_export_prices';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸入価格' WHERE econalpha_id = 'nz_import_prices';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '交易条件' WHERE econalpha_id = 'nz_terms_of_trade';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '建築許可件数' WHERE econalpha_id = 'nz_building_permits';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '総合PMI' WHERE econalpha_id = 'nz_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業PMI' WHERE econalpha_id = 'nz_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'サービス業PMI' WHERE econalpha_id = 'nz_services_pmi';

-- ============================================================================
-- CN (中国) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ローンプライムレート1年' WHERE econalpha_id = 'cn_lpr_1y';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'ローンプライムレート5年' WHERE econalpha_id = 'cn_lpr_5y';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'cn_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'cn_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'cn_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者物価指数（PPI）' WHERE econalpha_id = 'cn_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '鉱工業生産' WHERE econalpha_id = 'cn_industrial_production';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '工業利益' WHERE econalpha_id = 'cn_industrial_profits';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '鉱工業設備稼働率' WHERE econalpha_id = 'cn_capacity_utilization';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高' WHERE econalpha_id = 'cn_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '固定資産投資' WHERE econalpha_id = 'cn_fixed_asset_investment';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸出' WHERE econalpha_id = 'cn_exports';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '輸入' WHERE econalpha_id = 'cn_imports';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'M2マネーサプライ' WHERE econalpha_id = 'cn_m2_money_supply';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '社会融資総量' WHERE econalpha_id = 'cn_social_financing';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '外貨準備高' WHERE econalpha_id = 'cn_forex_reserves';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '住宅価格指数' WHERE econalpha_id = 'cn_house_price_index';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者信頼感' WHERE econalpha_id = 'cn_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業PMI' WHERE econalpha_id = 'cn_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'サービス業PMI' WHERE econalpha_id = 'cn_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PMI' WHERE econalpha_id = 'cn_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'NBS製造業PMI' WHERE econalpha_id = 'cn_nbs_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'NBS非製造業PMI' WHERE econalpha_id = 'cn_nbs_non_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'NBS総合PMI' WHERE econalpha_id = 'cn_nbs_general_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'Caixin総合PMI' WHERE econalpha_id = 'cn_caixin_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'Caixin製造業PMI' WHERE econalpha_id = 'cn_caixin_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'CaixinサービスPMI' WHERE econalpha_id = 'cn_caixin_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'S&Pグローバル総合PMI' WHERE econalpha_id = 'cn_sp_composite_pmi';

-- ============================================================================
-- CH (スイス) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'SNB金利決定' WHERE econalpha_id = 'ch_snb_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'ch_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'ch_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '雇用者数水準' WHERE econalpha_id = 'ch_employment_level';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '非農業部門雇用者数' WHERE econalpha_id = 'ch_nonfarm_payrolls';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'ch_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者・輸入物価' WHERE econalpha_id = 'ch_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '鉱工業生産' WHERE econalpha_id = 'ch_industrial_production';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '小売売上高' WHERE econalpha_id = 'ch_retail_sales';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者信頼感' WHERE econalpha_id = 'ch_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'SECO消費者景況感' WHERE econalpha_id = 'ch_seco_consumer_climate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'KOF先行指標' WHERE econalpha_id = 'ch_kof_leading';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'procure.ch製造業PMI' WHERE econalpha_id = 'ch_manufacturing_pmi';

-- ============================================================================
-- FR (フランス) - すべてフロントエンド未実装
-- ============================================================================
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'GDP成長率' WHERE econalpha_id = 'fr_gdp_growth';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業率' WHERE econalpha_id = 'fr_unemployment_rate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '非農業部門雇用者数' WHERE econalpha_id = 'fr_nonfarm_payrolls';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '失業給付申請件数' WHERE econalpha_id = 'fr_unemployment_claims';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者物価指数（CPI）' WHERE econalpha_id = 'fr_cpi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HICP' WHERE econalpha_id = 'fr_hicp';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '生産者物価指数（PPI）' WHERE econalpha_id = 'fr_ppi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '鉱工業生産' WHERE econalpha_id = 'fr_industrial_production';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者信頼感' WHERE econalpha_id = 'fr_consumer_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '消費者支出' WHERE econalpha_id = 'fr_consumer_spending';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '家計消費' WHERE econalpha_id = 'fr_household_consumption';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '企業信頼感' WHERE econalpha_id = 'fr_business_confidence';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '企業景況感指標' WHERE econalpha_id = 'fr_business_climate';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = '製造業PMI' WHERE econalpha_id = 'fr_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'サービス業PMI' WHERE econalpha_id = 'fr_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'PMI' WHERE econalpha_id = 'fr_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOB総合PMI' WHERE econalpha_id = 'fr_hcob_composite_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOB製造業PMI' WHERE econalpha_id = 'fr_hcob_manufacturing_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOBサービス業PMI' WHERE econalpha_id = 'fr_hcob_services_pmi';
UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = 'HCOB建設業PMI' WHERE econalpha_id = 'fr_hcob_construction_pmi';

-- ============================================================================
-- 更新結果確認
-- ============================================================================
SELECT
    country,
    COUNT(*) as total,
    COUNT(econalpha_id) as with_frontend_id,
    COUNT(*) - COUNT(econalpha_id) as without_frontend_id
FROM indicator_event_mapping
GROUP BY country
ORDER BY country;
