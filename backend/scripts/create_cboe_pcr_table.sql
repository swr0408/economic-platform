-- CBOE Put/Call Ratio テーブル
CREATE TABLE IF NOT EXISTS cboe_put_call_ratio (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    total_pcr NUMERIC(10, 4),
    source VARCHAR(50) DEFAULT 'CBOE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT cboe_put_call_ratio_date_unique UNIQUE (date)
);

CREATE INDEX IF NOT EXISTS idx_cboe_put_call_ratio_date
ON cboe_put_call_ratio (date DESC);
