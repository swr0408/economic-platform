-- 日本消費者物価指数の指標マッピング追加
-- jp_national_cpi: 全国CPI（月内で最初に発表されるCPI）
-- jp_tokyo_cpi: 東京都区部CPI（月内で2番目に発表されるCPI）
--
-- FMPでは両方とも 'CPI' イベントとして登録されている。
-- 分離ロジック（calendar_repository.py, fmp_next_release_utils.py）で
-- 月内の発表順序に基づいて全国/東京を判別する。

-- 全国CPI: FMPでは 'CPI' と 'Core CPI YoY' でマッチ
-- 月内で最初のCPI発表（18-21日頃）が全国CPI
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('jp_national_cpi', '全国消費者物価指数（CPI）', 'JP', 'monthly', ARRAY['CPI', 'Core CPI YoY'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    is_active = TRUE,
    updated_at = NOW();

-- 東京CPI: FMPでは 'CPI' と 'Core CPI YoY' でマッチ（全国CPIと同じパターン）
-- 月内で2番目のCPI発表（24-28日頃）が東京CPI
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES
    ('jp_tokyo_cpi', '東京都区部消費者物価指数（CPI）', 'JP', 'monthly', ARRAY['CPI', 'Core CPI YoY'], TRUE)
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = ARRAY['CPI', 'Core CPI YoY'],
    is_active = TRUE,
    updated_at = NOW();

-- 確認
SELECT econalpha_id, fmp_event_patterns, is_active FROM indicator_event_mapping WHERE econalpha_id LIKE 'jp%cpi%';
