-- eu_wage_growth (Eurostat賃金・給与) の indicator_event_mapping 追加
-- FMPのWage Growthイベントと紐付け

INSERT INTO indicator_event_mapping (
    econalpha_id,
    econalpha_name,
    country,
    frequency,
    fmp_event_patterns,
    is_active
) VALUES (
    'eu_wage_growth',
    '賃金上昇率（ユーロ圏）',
    'EU',
    'quarterly',
    ARRAY['Wage Growth YoY'],
    TRUE
)
ON CONFLICT (econalpha_id)
DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    is_active = TRUE,
    updated_at = NOW();

-- ecb_negotiated_wages (ECB交渉妥結賃金) の indicator_event_mapping 追加
-- FMPのNegotiated Wage Growthイベントと紐付け

INSERT INTO indicator_event_mapping (
    econalpha_id,
    econalpha_name,
    country,
    frequency,
    fmp_event_patterns,
    is_active
) VALUES (
    'ecb_negotiated_wages',
    '交渉妥結賃金（ユーロ圏）',
    'EU',
    'quarterly',
    ARRAY['Negotiated Wage Growth'],
    TRUE
)
ON CONFLICT (econalpha_id)
DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    is_active = TRUE,
    updated_at = NOW();
