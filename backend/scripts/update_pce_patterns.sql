-- Update PCE deflator FMP event patterns
UPDATE indicator_event_mapping
SET fmp_event_patterns = ARRAY['PCE Price Index MoM', 'PCE Price Index YoY', 'PCE Prices QoQ', 'Personal Income MoM'],
    updated_at = NOW()
WHERE econalpha_id = 'pce';

-- Verify
SELECT id, econalpha_id, econalpha_name, fmp_event_patterns, is_active
FROM indicator_event_mapping
WHERE econalpha_id = 'pce';
