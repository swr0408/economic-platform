-- Add PPI indicator event mapping
-- FMP event patterns for Producer Price Index

-- Check if mapping exists
SELECT id, econalpha_id, econalpha_name, fmp_event_patterns, is_active
FROM indicator_event_mapping
WHERE econalpha_id = 'ppi';

-- Insert or update PPI mapping
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, fmp_event_patterns, is_active, created_at, updated_at)
VALUES (
    'ppi',
    'Producer Price Index',
    ARRAY['Producer Price Index MoM', 'Producer Price Index YoY', 'PPI MoM', 'PPI YoY'],
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- Verify
SELECT id, econalpha_id, econalpha_name, fmp_event_patterns, is_active
FROM indicator_event_mapping
WHERE econalpha_id = 'ppi';
