-- ECB預金ファシリティ金利のindicator_event_mapping追加
-- 実行方法: psql -U postgres -d economic_platform -f add_ecb_rate_mapping.sql

-- 既存レコードがあれば更新、なければ挿入
INSERT INTO indicator_event_mapping (
    econalpha_id,
    econalpha_name,
    country,
    frequency,
    fmp_event_patterns,
    is_active,
    created_at,
    updated_at
)
VALUES (
    'eu_ecb_rate',
    'ECB預金ファシリティ金利',
    'EU',
    'irregular',
    ARRAY['ECB Interest Rate Decision', 'Interest Rate Decision', 'ECB Deposit Facility Rate', 'Deposit Facility Rate'],
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (econalpha_id) DO UPDATE SET
    econalpha_name = EXCLUDED.econalpha_name,
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- 結果確認
SELECT * FROM indicator_event_mapping WHERE econalpha_id = 'eu_ecb_rate';
