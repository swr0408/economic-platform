-- S&P Global PMI のindicator_event_mappingを追加
-- 3つのPMI指標（製造業、サービス業、総合）のマッピング

-- S&P Global 製造業PMI
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('sp_manufacturing_pmi', 'S&P Global 製造業PMI', 'US', 'monthly', ARRAY['S&P Global Manufacturing PMI'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- S&P Global サービス業PMI
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('sp_services_pmi', 'S&P Global サービス業PMI', 'US', 'monthly', ARRAY['S&P Global Services PMI'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- S&P Global 総合PMI
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('sp_composite_pmi', 'S&P Global 総合PMI', 'US', 'monthly', ARRAY['S&P Global Composite PMI'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 確認用クエリ
SELECT econalpha_id, econalpha_name, fmp_event_patterns
FROM indicator_event_mapping
WHERE econalpha_id LIKE 'sp_%pmi%'
ORDER BY econalpha_id;
