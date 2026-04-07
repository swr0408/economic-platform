-- BOJ Tankan (日銀短観) のindicator_event_mappingを追加
-- FMPイベント名: "Tankan Large Manufacturers Index", "Tankan Large Non-Manufacturers Index"

INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES ('boj_tankan', '日銀短観', 'JP', 'quarterly', ARRAY['Tankan Large Manufacturers Index', 'Tankan Large Non-Manufacturers Index'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();

-- 確認用クエリ
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns
FROM indicator_event_mapping
WHERE econalpha_id = 'boj_tankan';
