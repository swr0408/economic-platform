-- ドイツCPI/HICPの指標マッピング追加
-- germany_cpi を登録
-- FMPイベント名: CPI, Inflation Rate MoM, Inflation Rate YoY, HICP MoM, HICP YoY
-- country: DE

INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('germany_cpi', 'CPI / HICP（ドイツ）', 'DE', 'monthly', ARRAY['CPI', 'Inflation Rate MoM', 'Inflation Rate YoY', 'HICP MoM', 'HICP YoY'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- 確認
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns
FROM indicator_event_mapping
WHERE econalpha_id = 'germany_cpi';
