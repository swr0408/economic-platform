-- 日本有効求人倍率の指標マッピング追加
-- jp_job_offers_ratio を登録

INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('jp_job_offers_ratio', '有効求人倍率', 'JP', 'monthly', ARRAY['Jobs/applications ratio'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- 確認
SELECT econalpha_id, fmp_event_patterns FROM indicator_event_mapping WHERE econalpha_id = 'jp_job_offers_ratio';
