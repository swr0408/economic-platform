-- ドイツPPIの指標マッピング追加
-- germany_ppi を登録
-- FMPイベント名: PPI, PPI MoM, PPI YoY, Producer Prices
-- country: DE

INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('germany_ppi', 'PPI（ドイツ）', 'DE', 'monthly', ARRAY['PPI', 'PPI MoM', 'PPI YoY', 'Producer Prices'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- 確認
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns
FROM indicator_event_mapping
WHERE econalpha_id = 'germany_ppi';
