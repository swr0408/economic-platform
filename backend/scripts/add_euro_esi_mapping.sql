-- ============================================================================
-- Eurostat ESI (Economic Sentiment Indicator) マッピング追加
--
-- FMP経済カレンダーとの紐付け設定
-- マーケットインパクト分析用
-- ============================================================================

-- ESI マッピング追加
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES
    ('euro_esi', 'ESI（景況感指数）', 'EU', 'monthly', ARRAY['Economic Sentiment'], TRUE)
ON CONFLICT (econalpha_id)
DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    econalpha_name = EXCLUDED.econalpha_name,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- 確認用クエリ
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns, is_active
FROM indicator_event_mapping
WHERE econalpha_id = 'euro_esi';
