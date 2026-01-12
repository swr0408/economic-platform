-- ============================================================================
-- EU (ユーロ圏) マーケットインパクト用指標マッピング修正
--
-- update_indicator_names.sqlでeconalpha_idがNULLに設定されていたため、
-- マーケットインパクトタブで発表履歴が取得できない問題を修正
-- ============================================================================

-- GDP成長率
UPDATE indicator_event_mapping
SET econalpha_id = 'eu_gdp_growth'
WHERE country = 'EU'
  AND fmp_event_patterns @> ARRAY['GDP Growth Rate QoQ']
  AND econalpha_id IS NULL;

-- 鉱工業生産
UPDATE indicator_event_mapping
SET econalpha_id = 'eu_industrial_production'
WHERE country = 'EU'
  AND fmp_event_patterns @> ARRAY['Industrial Production MoM']
  AND econalpha_id IS NULL;

-- 確認用クエリ
SELECT econalpha_id, econalpha_name, country, fmp_event_patterns, is_active
FROM indicator_event_mapping
WHERE country = 'EU'
  AND econalpha_id IN ('eu_gdp_growth', 'eu_industrial_production');
