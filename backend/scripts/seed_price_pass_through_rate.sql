-- 価格転嫁率 初期データ投入（ハードコード → DB移行）
-- 冪等: ON CONFLICT DO NOTHING で何度実行しても安全

INSERT INTO price_pass_through_rate (survey_date, survey_period, total, raw_materials, energy, labor, zero_pass_through, supply_chain, source)
VALUES
    ('2023-03-01', '2023年3月',  47.6, 48.2, 35.0, 37.4, NULL, NULL, 'hardcoded'),
    ('2023-09-01', '2023年9月',  45.7, 45.4, 33.6, 36.7, NULL, NULL, 'hardcoded'),
    ('2024-03-01', '2024年3月',  46.1, 47.4, 40.4, 40.0, NULL, NULL, 'hardcoded'),
    ('2024-09-01', '2024年9月',  49.7, 51.4, 44.4, 44.7, NULL, '{"tier_1": 51.8, "tier_2": 46.1, "tier_3": 39.7, "tier_4_plus": 35.7}', 'hardcoded'),
    ('2025-03-01', '2025年3月',  52.4, 54.5, 47.8, 48.6, NULL, NULL, 'hardcoded'),
    ('2025-09-01', '2025年9月',  53.5, 55.0, 48.9, 50.0, 1.0,  NULL, 'hardcoded')
ON CONFLICT (survey_date) DO NOTHING;
