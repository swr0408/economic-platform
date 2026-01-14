-- 日本失業率の指標マッピング追加
-- jp_unemployment_rate を登録

INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('jp_unemployment_rate', '完全失業率', 'JP', 'monthly', ARRAY['Unemployment Rate'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- 確認
SELECT econalpha_id, fmp_event_patterns FROM indicator_event_mapping WHERE econalpha_id = 'jp_unemployment_rate';
