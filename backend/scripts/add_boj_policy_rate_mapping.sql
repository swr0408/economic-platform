-- BOJ Policy Rate のindicator_event_mappingを追加
-- 日銀政策金利のマッピング

-- BOJ Policy Rate
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('boj_policy_rate', '日銀政策金利', 'JP', 'irregular', ARRAY['BoJ Interest Rate Decision'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 確認用クエリ
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns
FROM indicator_event_mapping
WHERE econalpha_id = 'boj_policy_rate';
