-- 日本企業物価指数（CGPI）の指標マッピング追加
-- japan_cgpi: 日銀が発表する企業物価指数（Corporate Goods Price Index）
--
-- FMPでは 'Producer Price Index' イベントとして登録されている。
-- YoYとMoMの両方がマッチパターンに含まれる。

INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('japan_cgpi', '企業物価指数（CGPI）', 'JP', 'monthly', ARRAY['Producer Price Index MoM', 'Producer Price Index YoY'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    is_active = TRUE,
    updated_at = NOW();

-- 確認
SELECT econalpha_id, econalpha_name, fmp_event_patterns, is_active FROM indicator_event_mapping WHERE econalpha_id = 'japan_cgpi';
