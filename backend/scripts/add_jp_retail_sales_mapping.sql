-- 日本小売業販売額の指標マッピング追加
-- jp_retail_sales_mom と jp_retail_sales_yoy を個別登録

INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('jp_retail_sales_yoy', '小売業販売額（前年比）', 'JP', 'monthly', ARRAY['Retail Sales YoY']),
    ('jp_retail_sales_mom', '小売業販売額（前月比）', 'JP', 'monthly', ARRAY['Retail Sales MoM'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- 確認
SELECT econalpha_id, fmp_event_patterns FROM indicator_event_mapping WHERE econalpha_id LIKE 'jp_retail_sales%';
