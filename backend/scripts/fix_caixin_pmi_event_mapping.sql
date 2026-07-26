-- Caixin PMI (CN) の FMP イベント名改称対応 (2026-07-03)
--
-- FMP は Caixin China PMI を 2026 に "S&P Global Manufacturing/Services PMI"
-- (country=CN) へ改称し、"Caixin ..." 名イベントは 2026-02 で停止した。
-- indicator_event_mapping が旧名のみだと should_refresh_by_fmp_schedule /
-- get_next_release_from_fmp / resolve_last_updated_after_fetch が全て
-- 「直近発表なし」となり、発表日駆動の更新が沈黙する（max_age 24h のみで
-- ドリフト更新 → 発表時刻との衝突レースで旧月凍結。2026-07-03 サービス業で顕在化）。
-- 旧名+新名の両パターンを登録する（冪等）。

UPDATE indicator_event_mapping
SET fmp_event_patterns = ARRAY['Caixin Manufacturing PMI', 'S&P Global Manufacturing PMI'],
    updated_at = NOW()
WHERE econalpha_id = 'cn_caixin_manufacturing_pmi'
  AND NOT ('S&P Global Manufacturing PMI' = ANY(fmp_event_patterns));

UPDATE indicator_event_mapping
SET fmp_event_patterns = ARRAY['Caixin Services PMI', 'S&P Global Services PMI'],
    updated_at = NOW()
WHERE econalpha_id = 'cn_caixin_service_pmi'
  AND NOT ('S&P Global Services PMI' = ANY(fmp_event_patterns));
