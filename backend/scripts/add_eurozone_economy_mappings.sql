-- ユーロ圏経済指標のindicator_event_mapping追加
-- 実行方法: psql -U postgres -d economic_platform -f add_eurozone_economy_mappings.sql

-- ECB鉱工業生産
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
    'ecb_production',
    'ECB鉱工業生産',
    'EU',
    'monthly',
    ARRAY['Industrial Production MoM', 'Industrial Production YoY'],
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (econalpha_id) DO UPDATE SET
    econalpha_name = EXCLUDED.econalpha_name,
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- ECB銀行貸出調査
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
    'ecb_bls',
    'ECB銀行貸出調査',
    'EU',
    'quarterly',
    ARRAY['ECB Bank Lending Survey'],
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (econalpha_id) DO UPDATE SET
    econalpha_name = EXCLUDED.econalpha_name,
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- ユーロ圏GDP成長率
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
    'euro_gdp',
    'ユーロ圏GDP成長率',
    'EU',
    'quarterly',
    ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY', 'Gross Domestic Product QoQ', 'Gross Domestic Product YoY'],
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
SELECT * FROM indicator_event_mapping WHERE econalpha_id IN ('ecb_production', 'ecb_bls', 'euro_gdp');
