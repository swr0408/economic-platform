-- ============================================================================
-- Treasury Quarterly Refunding テーブル定義
-- 米財務省四半期リファンディング関連文書の構造化データ
-- ============================================================================

-- 1. メインイベントテーブル（文書ごとに1行）
CREATE TABLE IF NOT EXISTS treasury_quarterly_refunding_events (
    id              SERIAL PRIMARY KEY,
    quarter_label   TEXT NOT NULL,                -- "2026-Q1"
    published_at    TIMESTAMPTZ,                  -- 発表日時 (ET)
    document_type   TEXT NOT NULL,                -- financing_estimates / policy_statement / tbac_report / tbac_minutes
    title           TEXT,
    source_url      TEXT NOT NULL,                -- 原文URL
    raw_text        TEXT,                         -- 本文テキスト
    summary_text    TEXT,                         -- 要約（将来用）
    is_current      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(quarter_label, document_type)
);

CREATE INDEX IF NOT EXISTS ix_qr_events_quarter
ON treasury_quarterly_refunding_events(quarter_label DESC);

CREATE INDEX IF NOT EXISTS ix_qr_events_current
ON treasury_quarterly_refunding_events(is_current) WHERE is_current = TRUE;

-- 2. 構造化メトリクステーブル
CREATE TABLE IF NOT EXISTS treasury_quarterly_refunding_metrics (
    id              SERIAL PRIMARY KEY,
    event_id        INTEGER NOT NULL REFERENCES treasury_quarterly_refunding_events(id) ON DELETE CASCADE,
    metric_key      TEXT NOT NULL,                -- new_cash_raised, refunding_3y, etc.
    metric_value    NUMERIC(20,2),
    metric_unit     TEXT,                         -- billion_usd, percent, etc.
    metric_label    TEXT,                         -- 表示用ラベル
    UNIQUE(event_id, metric_key)
);

CREATE INDEX IF NOT EXISTS ix_qr_metrics_event
ON treasury_quarterly_refunding_metrics(event_id);

-- 3. 入札予定テーブル
CREATE TABLE IF NOT EXISTS treasury_auction_schedule (
    id                  SERIAL PRIMARY KEY,
    quarter_label       TEXT NOT NULL,
    security_term       TEXT,                     -- "3-Year", "13-Week"
    security_type       TEXT,                     -- BILL, NOTE, BOND
    reopening           BOOLEAN DEFAULT FALSE,
    is_tips             BOOLEAN DEFAULT FALSE,
    is_frn              BOOLEAN DEFAULT FALSE,
    announcement_date   DATE,
    auction_date        DATE,
    settlement_date     DATE,
    source_url          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(quarter_label, security_type, security_term, auction_date)
);

CREATE INDEX IF NOT EXISTS ix_auction_schedule_quarter
ON treasury_auction_schedule(quarter_label, auction_date);

-- 4. 買入予定テーブル
CREATE TABLE IF NOT EXISTS treasury_buyback_schedule (
    id                      SERIAL PRIMARY KEY,
    quarter_label           TEXT NOT NULL,
    purchase_bucket         TEXT,                 -- "5Y-7Y"
    security_type           TEXT,                 -- NOMINAL COUPONS, TIPS
    operation_type          TEXT,                 -- Liquidity Support, Cash Management
    min_amount              NUMERIC(20,2),        -- million USD
    max_amount              NUMERIC(20,2),        -- million USD
    maturity_range_start    DATE,
    maturity_range_end      DATE,
    announcement_date       DATE,
    operation_date          DATE,
    settlement_date         DATE,
    source_url              TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(quarter_label, purchase_bucket, operation_date)
);

CREATE INDEX IF NOT EXISTS ix_buyback_schedule_quarter
ON treasury_buyback_schedule(quarter_label, operation_date);

-- トリガー（updated_at自動更新）
DROP TRIGGER IF EXISTS update_qr_events_updated_at ON treasury_quarterly_refunding_events;
CREATE TRIGGER update_qr_events_updated_at
    BEFORE UPDATE ON treasury_quarterly_refunding_events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
