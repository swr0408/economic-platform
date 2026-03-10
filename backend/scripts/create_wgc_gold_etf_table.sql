-- WGC (World Gold Council) 金ETF保有残高・フローテーブル
-- 国別（11カ国）の月次/週次データ

CREATE TABLE IF NOT EXISTS wgc_gold_etf (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    frequency VARCHAR(10) NOT NULL DEFAULT 'monthly',
    country VARCHAR(30) NOT NULL,
    holdings_ton DOUBLE PRECISION,
    flows_ton DOUBLE PRECISION,
    flows_usd DOUBLE PRECISION,
    gold_price_usd DOUBLE PRECISION,
    source VARCHAR(50) DEFAULT 'WGC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, frequency, country)
);

CREATE INDEX IF NOT EXISTS idx_wgc_gold_etf_date ON wgc_gold_etf(date);
CREATE INDEX IF NOT EXISTS idx_wgc_gold_etf_freq_country ON wgc_gold_etf(frequency, country);
