-- ECB PPI（生産者物価指数）の指標マッピング追加
-- ecb_ppi を登録
-- FMPイベント名: Producer Price Index MoM, Producer Price Index YoY
-- country: EU

INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('ecb_ppi', 'PPI（ユーロ圏）', 'EU', 'monthly', ARRAY['Producer Price Index MoM', 'Producer Price Index YoY'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- 確認
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns
FROM indicator_event_mapping
WHERE econalpha_id = 'ecb_ppi';
