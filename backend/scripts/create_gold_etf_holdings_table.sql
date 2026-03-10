CREATE TABLE IF NOT EXISTS gold_etf_holdings (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    holdings_ton DOUBLE PRECISION,       -- 金保有量（トン）
    nav_usd DOUBLE PRECISION,            -- 信託総純資産額（USD）
    close_usd DOUBLE PRECISION,          -- 1326終値（USD）
    close_jpy DOUBLE PRECISION,          -- 1326終値（円）
    gold_price_usd DOUBLE PRECISION,     -- ドル建て金価格（yfinance GC=F）
    source VARCHAR(50) DEFAULT 'SPDR',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date)
);

CREATE INDEX IF NOT EXISTS idx_gold_etf_holdings_date ON gold_etf_holdings(date);
