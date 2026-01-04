-- indicator_event_mapping にマーケットインパクト用のマッピングを追加
-- FMPイベント名とEconAlpha指標IDの紐付け

-- フルタイム / パートタイム雇用者数（fulltime_employment）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('fulltime_employment', 'フルタイム/パートタイム雇用者数', 'US', 'monthly', ARRAY['Nonfarm Payrolls'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 複数の仕事を持つ人 / 経済的理由によるパートタイム（multiple_jobs）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('multiple_jobs', '複数の仕事を持つ人/経済的理由によるパートタイム', 'US', 'monthly', ARRAY['Nonfarm Payrolls'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 平均時給（average_hourly_earnings_yoy）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('average_hourly_earnings_yoy', '平均時給（前年比）', 'US', 'monthly', ARRAY['Average Hourly Earnings YoY'], TRUE)
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

-- 家計貯蓄率（personal_saving_rate）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('personal_saving_rate', '家計貯蓄率', 'US', 'monthly', ARRAY['Personal Spending MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 個人所得（personal_income_mom）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('personal_income_mom', '個人所得', 'US', 'monthly', ARRAY['Personal Income MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 可処分所得（disposable_income）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('disposable_income', '可処分所得', 'US', 'monthly', ARRAY['Personal Income MoM'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 個人消費支出 PCE（pce_mom）
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('pce_mom', '個人消費支出（PCE）', 'US', 'monthly', ARRAY['Personal Spending MoM', 'Core PCE Price Index MoM'], TRUE)
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

-- 確認用クエリ
SELECT econalpha_id, econalpha_name, fmp_event_patterns FROM indicator_event_mapping WHERE country = 'US' ORDER BY econalpha_id;
