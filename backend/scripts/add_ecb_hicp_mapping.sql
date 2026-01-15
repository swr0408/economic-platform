-- ECB HICP（消費者物価調和指数）の指標マッピング追加
-- ecb_hicp を登録
-- FMPイベント名: HICP MoM, HICP YoY
-- country: EU

INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('ecb_hicp', 'HICP（ユーロ圏）', 'EU', 'monthly', ARRAY['HICP MoM', 'HICP YoY'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- 確認
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns
FROM indicator_event_mapping
WHERE econalpha_id = 'ecb_hicp';
