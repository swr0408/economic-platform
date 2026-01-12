-- ============================================================================
-- ECB Retail Trade (小売売上高) マッピング追加
--
-- FMP経済カレンダーとの紐付け設定
-- マーケットインパクト分析用
-- ============================================================================

-- ECB Retail Trade マッピング追加
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES
    ('ecb_retail_trade', '小売売上高（ユーロ圏）', 'EU', 'monthly', ARRAY['Retail Sales'], TRUE)
ON CONFLICT (econalpha_id)
DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    econalpha_name = EXCLUDED.econalpha_name,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- 確認用クエリ
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns, is_active
FROM indicator_event_mapping
WHERE econalpha_id = 'ecb_retail_trade';
