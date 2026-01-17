-- BOE Economic Outlook (BOE経済見通し) のindicator_event_mappingを追加
-- BOE Monetary Policy Report (MPR) のマッピング
-- 更新スケジュール: 2月/5月/8月/11月（MPR公表月）、20:00-20:10 ロンドン時間

-- BOE Economic Outlook (Market Expectations, CPI Projections, GDP Forecast, Unemployment Forecast)
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('boe_economic_outlook', 'BOE経済見通し', 'UK', 'quarterly', ARRAY['BoE Monetary Policy Report'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 確認用クエリ
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns
FROM indicator_event_mapping
WHERE econalpha_id = 'boe_economic_outlook';
