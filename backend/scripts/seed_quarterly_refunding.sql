-- ============================================================================
-- Treasury Quarterly Refunding 初期データ (2026-Q1)
-- 冪等: ON CONFLICT DO NOTHING
-- ============================================================================

-- まず全既存データのis_currentをFALSEに
UPDATE treasury_quarterly_refunding_events SET is_current = FALSE WHERE is_current = TRUE;

-- Policy Statement
INSERT INTO treasury_quarterly_refunding_events
    (quarter_label, published_at, document_type, title, source_url, is_current)
VALUES
    ('2026-Q1', '2026-02-04 13:30:00+00', 'policy_statement',
     'Quarterly Refunding Statement of Deputy Assistant Secretary for Federal Finance Brian Smith',
     'https://home.treasury.gov/news/press-releases/sb0384', TRUE)
ON CONFLICT (quarter_label, document_type) DO UPDATE SET
    is_current = TRUE,
    updated_at = NOW();

-- Financing Estimates
INSERT INTO treasury_quarterly_refunding_events
    (quarter_label, published_at, document_type, title, source_url, is_current)
VALUES
    ('2026-Q1', '2026-02-02 20:00:00+00', 'financing_estimates',
     'Treasury Marketable Borrowing Estimates',
     'https://home.treasury.gov/news/press-releases/sb0377', TRUE)
ON CONFLICT (quarter_label, document_type) DO UPDATE SET
    is_current = TRUE,
    updated_at = NOW();

-- TBAC Report
INSERT INTO treasury_quarterly_refunding_events
    (quarter_label, published_at, document_type, title, source_url, is_current)
VALUES
    ('2026-Q1', '2026-02-04 13:30:00+00', 'tbac_report',
     'Report to the Secretary of the Treasury from the Treasury Borrowing Advisory Committee',
     'https://home.treasury.gov/news/press-releases/sb0385', TRUE)
ON CONFLICT (quarter_label, document_type) DO UPDATE SET
    is_current = TRUE,
    updated_at = NOW();

-- TBAC Minutes
INSERT INTO treasury_quarterly_refunding_events
    (quarter_label, published_at, document_type, title, source_url, is_current)
VALUES
    ('2026-Q1', '2026-02-04 13:30:00+00', 'tbac_minutes',
     'Minutes of the Meeting of the Treasury Borrowing Advisory Committee',
     'https://home.treasury.gov/news/press-releases/sb0386', TRUE)
ON CONFLICT (quarter_label, document_type) DO UPDATE SET
    is_current = TRUE,
    updated_at = NOW();

-- Policy Statement メトリクス
DO $$
DECLARE
    v_event_id INTEGER;
BEGIN
    SELECT id INTO v_event_id FROM treasury_quarterly_refunding_events
    WHERE quarter_label = '2026-Q1' AND document_type = 'policy_statement';

    IF v_event_id IS NOT NULL THEN
        INSERT INTO treasury_quarterly_refunding_metrics (event_id, metric_key, metric_value, metric_unit, metric_label)
        VALUES
            (v_event_id, 'refunding_total', 125.0, 'billion_usd', 'Total Offering'),
            (v_event_id, 'new_cash_raised', 34.8, 'billion_usd', 'New Cash Raised'),
            (v_event_id, 'maturing_securities', 90.2, 'billion_usd', 'Maturing Securities'),
            (v_event_id, 'refunding_3y', 58.0, 'billion_usd', '3-Year Note'),
            (v_event_id, 'refunding_10y', 42.0, 'billion_usd', '10-Year Note'),
            (v_event_id, 'refunding_30y', 25.0, 'billion_usd', '30-Year Bond'),
            (v_event_id, 'buyback_liquidity_max', 38.0, 'billion_usd', 'Buyback Liquidity Support Max'),
            (v_event_id, 'buyback_cash_mgmt_max', 75.0, 'billion_usd', 'Buyback Cash Management Max'),
            (v_event_id, 'cash_balance_eom', 850.0, 'billion_usd', 'Assumed End-of-March Cash Balance'),
            -- Auction size table (Feb-Apr 2026)
            (v_event_id, 'auction_size_2y_202602', 69.0, 'billion_usd', '2Y Feb-26'),
            (v_event_id, 'auction_size_3y_202602', 58.0, 'billion_usd', '3Y Feb-26'),
            (v_event_id, 'auction_size_5y_202602', 70.0, 'billion_usd', '5Y Feb-26'),
            (v_event_id, 'auction_size_7y_202602', 44.0, 'billion_usd', '7Y Feb-26'),
            (v_event_id, 'auction_size_10y_202602', 42.0, 'billion_usd', '10Y Feb-26'),
            (v_event_id, 'auction_size_20y_202602', 16.0, 'billion_usd', '20Y Feb-26'),
            (v_event_id, 'auction_size_30y_202602', 25.0, 'billion_usd', '30Y Feb-26'),
            (v_event_id, 'auction_size_frn_202602', 28.0, 'billion_usd', 'FRN Feb-26'),
            (v_event_id, 'auction_size_2y_202603', 69.0, 'billion_usd', '2Y Mar-26'),
            (v_event_id, 'auction_size_3y_202603', 58.0, 'billion_usd', '3Y Mar-26'),
            (v_event_id, 'auction_size_5y_202603', 70.0, 'billion_usd', '5Y Mar-26'),
            (v_event_id, 'auction_size_7y_202603', 44.0, 'billion_usd', '7Y Mar-26'),
            (v_event_id, 'auction_size_10y_202603', 39.0, 'billion_usd', '10Y Mar-26'),
            (v_event_id, 'auction_size_20y_202603', 13.0, 'billion_usd', '20Y Mar-26'),
            (v_event_id, 'auction_size_30y_202603', 22.0, 'billion_usd', '30Y Mar-26'),
            (v_event_id, 'auction_size_frn_202603', 28.0, 'billion_usd', 'FRN Mar-26'),
            (v_event_id, 'auction_size_2y_202604', 69.0, 'billion_usd', '2Y Apr-26'),
            (v_event_id, 'auction_size_3y_202604', 58.0, 'billion_usd', '3Y Apr-26'),
            (v_event_id, 'auction_size_5y_202604', 70.0, 'billion_usd', '5Y Apr-26'),
            (v_event_id, 'auction_size_7y_202604', 44.0, 'billion_usd', '7Y Apr-26'),
            (v_event_id, 'auction_size_10y_202604', 39.0, 'billion_usd', '10Y Apr-26'),
            (v_event_id, 'auction_size_20y_202604', 13.0, 'billion_usd', '20Y Apr-26'),
            (v_event_id, 'auction_size_30y_202604', 22.0, 'billion_usd', '30Y Apr-26'),
            (v_event_id, 'auction_size_frn_202604', 30.0, 'billion_usd', 'FRN Apr-26'),
            -- 前3ヶ月 (Nov-25〜Jan-26)
            (v_event_id, 'auction_size_2y_202511', 69.0, 'billion_usd', '2Y Nov-25'),
            (v_event_id, 'auction_size_3y_202511', 58.0, 'billion_usd', '3Y Nov-25'),
            (v_event_id, 'auction_size_5y_202511', 70.0, 'billion_usd', '5Y Nov-25'),
            (v_event_id, 'auction_size_7y_202511', 44.0, 'billion_usd', '7Y Nov-25'),
            (v_event_id, 'auction_size_10y_202511', 42.0, 'billion_usd', '10Y Nov-25'),
            (v_event_id, 'auction_size_20y_202511', 16.0, 'billion_usd', '20Y Nov-25'),
            (v_event_id, 'auction_size_30y_202511', 25.0, 'billion_usd', '30Y Nov-25'),
            (v_event_id, 'auction_size_frn_202511', 28.0, 'billion_usd', 'FRN Nov-25'),
            (v_event_id, 'auction_size_2y_202512', 69.0, 'billion_usd', '2Y Dec-25'),
            (v_event_id, 'auction_size_3y_202512', 58.0, 'billion_usd', '3Y Dec-25'),
            (v_event_id, 'auction_size_5y_202512', 70.0, 'billion_usd', '5Y Dec-25'),
            (v_event_id, 'auction_size_7y_202512', 44.0, 'billion_usd', '7Y Dec-25'),
            (v_event_id, 'auction_size_10y_202512', 39.0, 'billion_usd', '10Y Dec-25'),
            (v_event_id, 'auction_size_20y_202512', 13.0, 'billion_usd', '20Y Dec-25'),
            (v_event_id, 'auction_size_30y_202512', 22.0, 'billion_usd', '30Y Dec-25'),
            (v_event_id, 'auction_size_frn_202512', 28.0, 'billion_usd', 'FRN Dec-25'),
            (v_event_id, 'auction_size_2y_202601', 69.0, 'billion_usd', '2Y Jan-26'),
            (v_event_id, 'auction_size_3y_202601', 58.0, 'billion_usd', '3Y Jan-26'),
            (v_event_id, 'auction_size_5y_202601', 70.0, 'billion_usd', '5Y Jan-26'),
            (v_event_id, 'auction_size_7y_202601', 44.0, 'billion_usd', '7Y Jan-26'),
            (v_event_id, 'auction_size_10y_202601', 39.0, 'billion_usd', '10Y Jan-26'),
            (v_event_id, 'auction_size_20y_202601', 13.0, 'billion_usd', '20Y Jan-26'),
            (v_event_id, 'auction_size_30y_202601', 22.0, 'billion_usd', '30Y Jan-26'),
            (v_event_id, 'auction_size_frn_202601', 30.0, 'billion_usd', 'FRN Jan-26')
        ON CONFLICT (event_id, metric_key) DO NOTHING;
    END IF;
END $$;

-- Financing Estimates メトリクス
DO $$
DECLARE
    v_event_id INTEGER;
BEGIN
    SELECT id INTO v_event_id FROM treasury_quarterly_refunding_events
    WHERE quarter_label = '2026-Q1' AND document_type = 'financing_estimates';

    IF v_event_id IS NOT NULL THEN
        INSERT INTO treasury_quarterly_refunding_metrics (event_id, metric_key, metric_value, metric_unit, metric_label)
        VALUES
            (v_event_id, 'borrowing_estimate_current_qtr', 574.0, 'billion_usd', 'Jan-Mar 2026 Borrowing Estimate'),
            (v_event_id, 'borrowing_estimate_next_qtr', 109.0, 'billion_usd', 'Apr-Jun 2026 Borrowing Estimate'),
            (v_event_id, 'assumed_end_cash_balance_current_qtr', 850.0, 'billion_usd', 'Assumed End-of-March Cash Balance'),
            (v_event_id, 'assumed_end_cash_balance_next_qtr', 900.0, 'billion_usd', 'Assumed End-of-June Cash Balance'),
            (v_event_id, 'actual_borrowing_prev_qtr', 550.0, 'billion_usd', 'Oct-Dec 2025 Actual Borrowing'),
            (v_event_id, 'prev_estimate_current_qtr', 577.0, 'billion_usd', 'Previous Estimate (Nov 2025)')
        ON CONFLICT (event_id, metric_key) DO NOTHING;
    END IF;
END $$;
