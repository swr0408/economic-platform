-- indicator_event_mapping にマーケットインパクト用のマッピングを追加
-- FMPイベント名とEconAlpha指標IDの紐付け

-- フルタイム / パートタイム雇用者数（fulltime_employment）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('fulltime_employment', 'フルタイム/パートタイム雇用者数', 'US', 'monthly', ARRAY['Non Farm Payrolls', 'Nonfarm Payrolls'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 複数の仕事を持つ人 / 経済的理由によるパートタイム（multiple_jobs）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('multiple_jobs', '複数の仕事を持つ人/経済的理由によるパートタイム', 'US', 'monthly', ARRAY['Non Farm Payrolls', 'Nonfarm Payrolls'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 平均時給（average_hourly_earnings_yoy）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('average_hourly_earnings_yoy', '平均時給（前年比）', 'US', 'monthly', ARRAY['Average Hourly Earnings YoY', 'Average Hourly Earnings'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 労働参加率（labor_force_participation）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('labor_force_participation', '労働参加率', 'US', 'monthly', ARRAY['Labor Force Participation Rate'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 単位労働コスト / 労働生産性（unit_labor_cost）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('unit_labor_cost', '単位労働コスト', 'US', 'quarterly', ARRAY['Unit Labor Costs QoQ', 'Nonfarm Productivity QoQ'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 小売売上高（retail_sales_mom）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('retail_sales_mom', '小売売上高', 'US', 'monthly', ARRAY['Retail Sales MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 家計貯蓄率（personal_saving_rate）→ 個人所得と同時発表
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('personal_saving_rate', '家計貯蓄率', 'US', 'monthly', ARRAY['Personal Income MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 個人所得（personal_income_mom）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('personal_income_mom', '個人所得', 'US', 'monthly', ARRAY['Personal Income MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 可処分所得（disposable_income）→ 個人所得と同時発表
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('disposable_income', '可処分所得', 'US', 'monthly', ARRAY['Personal Income MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 個人消費支出 PCE（pce_mom）→ 個人所得と同時発表
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('pce_mom', '個人消費支出（PCE）', 'US', 'monthly', ARRAY['Personal Income MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 鉱工業生産（industrial_production_yoy）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('industrial_production_yoy', '鉱工業生産', 'US', 'monthly', ARRAY['Industrial Production YoY', 'Industrial Production MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 耐久財受注（durable_goods_mom）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('durable_goods_mom', '耐久財受注', 'US', 'monthly', ARRAY['Durable Goods Orders MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ADP雇用者数（adp_employment）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('adp_employment', 'ADP雇用者数', 'US', 'monthly', ARRAY['ADP Employment Change'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 非農業部門雇用者数（nonfarm_payrolls）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('nonfarm_payrolls', '非農業部門雇用者数', 'US', 'monthly', ARRAY['Nonfarm Payrolls'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 失業率（unemployment_rate）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('unemployment_rate', '失業率', 'US', 'monthly', ARRAY['Unemployment Rate'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 新規失業保険申請件数（initial_claims）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('initial_claims', '新規失業保険申請件数', 'US', 'weekly', ARRAY['Initial Jobless Claims'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 継続失業保険申請件数（continued_claims）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('continued_claims', '継続失業保険申請件数', 'US', 'weekly', ARRAY['Continuing Jobless Claims'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 雇用コスト指数（employment_cost_index）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('employment_cost_index', '雇用コスト指数', 'US', 'quarterly', ARRAY['Employment Cost Index QoQ'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- GDP成長率（gdp_growth）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('gdp_growth', 'GDP成長率', 'US', 'quarterly', ARRAY['GDP Growth Rate QoQ', 'GDP Growth Annualized'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 設備稼働率（capacity_utilization）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('capacity_utilization', '設備稼働率', 'US', 'monthly', ARRAY['Capacity Utilization Rate'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ミシガン大学消費者信頼感指数（michigan_consumer_sentiment）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('michigan_consumer_sentiment', 'ミシガン大学消費者信頼感指数', 'US', 'monthly', ARRAY['Michigan Consumer Sentiment'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ミシガン大学インフレ期待（michigan_inflation_expectations）
-- 消費者信頼感と同時発表のため同じイベントパターンを使用
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('michigan_inflation_expectations', 'ミシガン大学インフレ期待', 'US', 'monthly', ARRAY['Michigan Consumer Sentiment', 'Michigan Inflation Expectations'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- JOLTS求人件数（jolts_openings）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('jolts_openings', 'JOLTS求人件数', 'US', 'monthly', ARRAY['JOLTs Job Openings'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- フィラデルフィア連銀景況指数（philadelphia_fed）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('philadelphia_fed', 'フィラデルフィア連銀景況指数', 'US', 'monthly', ARRAY['Philadelphia Fed Manufacturing Index'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- NY連銀製造業景況指数（empire_state）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('empire_state', 'NY連銀製造業景況指数', 'US', 'monthly', ARRAY['NY Empire State Manufacturing Index'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- NFIB中小企業楽観指数（nfib）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('nfib', 'NFIB中小企業楽観指数', 'US', 'monthly', ARRAY['NFIB Business Optimism Index'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- CB消費者信頼感指数（cb_consumer_confidence）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cb_consumer_confidence', 'CB消費者信頼感指数', 'US', 'monthly', ARRAY['CB Consumer Confidence'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- レッドブック（redbook）- 前年比
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('redbook', 'レッドブック（前年比）', 'US', 'weekly', ARRAY['Redbook YoY', 'Redbook'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- チャレンジャー人員削減数（challenger_job_cuts）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('challenger_job_cuts', 'チャレンジャー人員削減数', 'US', 'monthly', ARRAY['Challenger Job Cuts', 'Challenger Job Cuts YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ISM製造業景況指数（ism_manufacturing）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('ism_manufacturing', 'ISM製造業景況指数', 'US', 'monthly', ARRAY['ISM Manufacturing PMI', 'ISM Manufacturing'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ISM非製造業景況指数（ism_non_manufacturing）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('ism_non_manufacturing', 'ISM非製造業景況指数', 'US', 'monthly', ARRAY['ISM Non-Manufacturing PMI', 'ISM Services PMI', 'ISM Non-Manufacturing'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 政策金利（policy_rate）- FRB
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('policy_rate', '政策金利（FRB）', 'US', 'as_needed', ARRAY['Fed Interest Rate Decision', 'FOMC', 'Federal Funds Rate'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 消費者物価指数 CPI（us_cpi）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('us_cpi', '消費者物価指数（CPI）', 'US', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- コアCPI（us_core_cpi）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('us_core_cpi', 'コアCPI', 'US', 'monthly', ARRAY['Core Inflation Rate MoM', 'Core Inflation Rate YoY', 'Core CPI MoM', 'Core CPI YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- =============================================================================
-- ドイツ（DE）指標
-- =============================================================================

-- ドイツGfK消費者信頼感指数（germany_consumer_confidence_gfk）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('germany_consumer_confidence_gfk', 'ドイツGfK消費者信頼感指数', 'DE', 'monthly', ARRAY['GfK Consumer Confidence', 'Consumer Confidence'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ドイツ製造業新規受注（germany_factory_orders）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('germany_factory_orders', 'ドイツ製造業新規受注', 'DE', 'monthly', ARRAY['German Factory Orders', 'Factory Orders MoM', 'Factory Orders YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ドイツ鉱工業生産（germany_industrial_production）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('germany_industrial_production', 'ドイツ鉱工業生産', 'DE', 'monthly', ARRAY['German Industrial Production', 'Industrial Production MoM', 'Industrial Production YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ZEW景況感指数（zew_economic_sentiment_index）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('zew_economic_sentiment_index', 'ZEW景況感指数', 'DE', 'monthly', ARRAY['ZEW Economic Sentiment Index'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- =============================================================================
-- イギリス（UK）指標
-- =============================================================================

-- CBI製造業受注指数（cbi_industrial_trends）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cbi_industrial_trends', 'CBI製造業受注指数', 'UK', 'monthly', ARRAY['CBI Industrial Trends Orders', 'CBI Business Optimism Index'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- UK PMI（製造業・サービス業・総合）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('uk_pmi', 'UK PMI（製造業・サービス業・総合）', 'UK', 'monthly', ARRAY['S&P Global Manufacturing PMI', 'S&P Global Services PMI', 'S&P Global Composite PMI'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- =============================================================================
-- 日本（Japan）指標
-- =============================================================================

-- 日本鉱工業生産（jp_industrial_production）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('jp_industrial_production', '日本鉱工業生産', 'JP', 'monthly', ARRAY['Industrial Production MoM', 'Industrial Production YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 日本第三次産業活動指数（jp_tertiary_industry_index）※バックエンドサービス用
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('jp_tertiary_industry_index', '日本第三次産業活動指数', 'JP', 'monthly', ARRAY['Tertiary Industry Index MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 日本第三次産業活動指数（japan_tertiary_industry）※マーケットインパクト用
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('japan_tertiary_industry', '日本第三次産業活動指数', 'JP', 'monthly', ARRAY['Tertiary Industry Index MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- =============================================================================
-- ユーロ圏（Eurozone）指標
-- =============================================================================

-- ECB M3マネーサプライ（monetary_aggregate_m3）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('monetary_aggregate_m3', 'M3マネーサプライ前年比', 'EU', 'monthly', ARRAY['M3 Money Supply YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ECB調整済貸出（ecb_adjusted_loans）- M3マネーサプライと同時発表
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('ecb_adjusted_loans', '調整済貸出（ユーロ圏）', 'EU', 'monthly', ARRAY['M3 Money Supply YoY', 'M3 Money Supply'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- EU国際貿易（eu_international_trade）- 貿易収支・輸出・輸入
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('eu_international_trade', 'EU国際貿易', 'EU', 'monthly', ARRAY['Balance of Trade'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- EU経常収支（eu_current_account_balance）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('eu_current_account_balance', '経常収支（ユーロ圏）', 'EU', 'monthly', ARRAY['Current Account'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- スペインHICP/CPI（spain_hicp_cpi）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('spain_hicp_cpi', 'HICP/CPI（スペイン）', 'ES', 'monthly', ARRAY['CPI', 'HICP', 'Inflation Rate', 'Core Inflation Rate'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- UK公的部門純借入（uk_public_sector_net_borrowing_ex_bank）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('uk_public_sector_net_borrowing_ex_bank', '公的部門純借入（イギリス）', 'GB', 'monthly', ARRAY['Public Sector Net Borrowing'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- UK貿易収支（uk_trade_balance）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('uk_trade_balance', '貿易収支（イギリス）', 'GB', 'monthly', ARRAY['Trade Balance'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- UK経常収支（uk_current_account）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('uk_current_account', '経常収支（イギリス）', 'GB', 'quarterly', ARRAY['Current Account'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- UK政府債務残高対GDP比（uk_government_debt_to_gdp_ratio）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('uk_government_debt_to_gdp_ratio', '政府債務残高対GDP比（イギリス）', 'GB', 'monthly', ARRAY['Public Sector Net Borrowing'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 日本経常収支（japan_current_account）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('japan_current_account', '経常収支（日本）', 'JP', 'monthly', ARRAY['Current Account'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 日本貿易収支（japan_balance_of_trade）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('japan_balance_of_trade', '貿易収支（日本）', 'JP', 'monthly', ARRAY['Balance of Trade'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- スイス貿易収支（ch_balance_of_trade）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('ch_balance_of_trade', '貿易収支（スイス）', 'CH', 'monthly', ARRAY['Balance of Trade'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- スイス経常収支（ch_current_account）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('ch_current_account', '経常収支（スイス）', 'CH', 'quarterly', ARRAY['Current Account'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- オーストラリア貿易収支（au_international_trade）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('au_international_trade', '貿易収支（オーストラリア）', 'AU', 'monthly', ARRAY['Balance of Trade'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- オーストラリア経常収支（au_current_account）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('au_current_account', '経常収支（オーストラリア）', 'AU', 'quarterly', ARRAY['Current Account'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ニュージーランド 乳製品価格（GDT）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('nz_global_dairy_trade', '乳製品価格（GDT）', 'NZ', 'irregular', ARRAY['GlobalDairyTrade Price Index'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ニュージーランド 経常収支（nz_current_account_balance）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('nz_current_account_balance', '経常収支（ニュージーランド）', 'NZ', 'quarterly', ARRAY['Current Account'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 中国 新規人民元貸出（cn_new_rmb_loans）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cn_new_rmb_loans', '新規人民元貸出', 'CN', 'monthly', ARRAY['New Yuan Loans', 'New Loans'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 中国 LPR 1年（cn_lpr_1y）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cn_lpr_1y', 'ローンプライムレート（1年）', 'CN', 'monthly', ARRAY['Loan Prime Rate 1Y'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 中国 LPR 5年（cn_lpr_5y）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cn_lpr_5y', 'ローンプライムレート（5年）', 'CN', 'monthly', ARRAY['Loan Prime Rate 5Y'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 中国 外貨準備（cn_foreign_exchange_reserves）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cn_foreign_exchange_reserves', '外貨準備高', 'CN', 'monthly', ARRAY['Foreign Exchange Reserves'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 中国 経常収支（cn_current_account）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cn_current_account', '経常収支', 'CN', 'quarterly', ARRAY['Current Account'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 中国 住宅価格指数（cn_house_price_index）
-- NBS序号9: 商品住宅销售价格指数月度报告
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cn_house_price_index', '住宅価格指数', 'CN', 'monthly', ARRAY['House Price Index YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 中国 商業住宅販売（cn_commercial_residential_sales）
-- NBS序号10: 房地产开发和销售情况月度报告 — 住宅価格指数と同日発表
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cn_commercial_residential_sales', '商業住宅販売', 'CN', 'monthly', ARRAY['House Price Index YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 台湾PMI先行き・電子工学業（taiwan_pmi_outlook）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('taiwan_pmi_outlook', '台湾PMI先行き（電子工学業）', 'TW', 'monthly', ARRAY['S&P Global Manufacturing PMI'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 韓国輸出（south_korean_exports）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('south_korean_exports', '韓国輸出', 'KR', 'monthly', ARRAY['Exports YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 台湾輸出受注（taiwan_export_orders）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('taiwan_export_orders', '台湾輸出受注', 'TW', 'monthly', ARRAY['Export Orders YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 週間原油在庫（weekly_crude_oil_inventories）
-- EIA Weekly Crude Oil Inventories - 毎週水曜 15:30 UTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('weekly_crude_oil_inventories', '週間原油在庫（EIA）', 'US', 'weekly', ARRAY['EIA Crude Oil Stocks Change'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- クッシング原油在庫（us_cushing_inventory）
-- EIA Cushing Crude Oil Stocks Change - 毎週水曜 15:30 UTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('us_cushing_inventory', 'クッシング原油在庫（EIA）', 'US', 'weekly', ARRAY['EIA Cushing Crude Oil Stocks Change'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 米国蒸留燃料在庫（us_distillate_fuel_inventories）
-- EIA Distillate Fuel Production Change - 毎週水曜 15:30 UTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('us_distillate_fuel_inventories', '蒸留燃料在庫（EIA）', 'US', 'weekly', ARRAY['EIA Distillate Fuel Production Change'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 米国ガソリン在庫/製油稼働率（us_gasoline_inventories_refinery_utilization_rate）
-- EIA Gasoline Production Change - 毎週水曜 15:30 UTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('us_gasoline_inventories_refinery_utilization_rate', 'ガソリン在庫/製油稼働率（EIA）', 'US', 'weekly', ARRAY['EIA Gasoline Production Change'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- API（米国石油協会）週間原油在庫（api_weekly_crude_oil_inventories）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('api_weekly_crude_oil_inventories', 'API週間原油在庫', 'US', 'weekly', ARRAY['API Crude Oil Stock Change'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 米石油採掘装置（リグ）稼働数（north_america_rig_count）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('north_america_rig_count', '米石油リグ稼働数', 'US', 'weekly', ARRAY['Baker Hughes Oil Rig Count'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 米国天然ガス貯蔵量（us_natural_gas_storage）
-- EIA Natural Gas Stocks Change - 毎週木曜 15:30 UTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('us_natural_gas_storage', '米国天然ガス貯蔵量（EIA）', 'US', 'weekly', ARRAY['EIA Natural Gas Stocks Change'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ===== CFTC Positioning (投機筋ポジション) =====

-- 金 CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_gold', '金 CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC Gold Speculative net positions', 'CFTC Gold speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 銀 CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_silver', '銀 CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC Silver Speculative net positions', 'CFTC Silver speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 銅 CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_copper', '銅 CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC Copper speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 原油 CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_crude_oil', '原油 CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC Crude Oil speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 天然ガス CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_natural_gas', '天然ガス CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC Natural Gas speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- S&P 500 CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_sp500', 'S&P 500 CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC S&P 500 speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ナスダック100 CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_nasdaq100', 'ナスダック100 CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC Nasdaq 100 speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ドル/円 CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_usdjpy', '円 CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC JPY speculative net positions', 'CFTC Jpy speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ユーロ CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_eurusd', 'ユーロ CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC EUR speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- ポンド CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_gbpusd', 'ポンド CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC GBP speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 豪ドル CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_audusd', '豪ドル CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC AUD speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- NZドル CFTC
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('cftc_nzdusd', 'NZドル CFTC投機筋ポジション', 'US', 'weekly', ARRAY['CFTC NZD speculative net positions'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 確認用クエリ
SELECT econalpha_id, econalpha_name, fmp_event_patterns FROM indicator_event_mapping WHERE country IN ('US', 'CN', 'TW', 'KR') ORDER BY country, econalpha_id;
