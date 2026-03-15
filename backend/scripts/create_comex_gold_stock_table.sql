-- COMEX Gold Stock テーブル
CREATE TABLE IF NOT EXISTS comex_gold_stock (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    registered_oz DOUBLE PRECISION,
    eligible_oz DOUBLE PRECISION,
    total_oz DOUBLE PRECISION,
    source VARCHAR(50) DEFAULT 'CME',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date)
);
CREATE INDEX IF NOT EXISTS idx_comex_gold_stock_date ON comex_gold_stock(date);

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE comex_gold_stock TO economic;
GRANT USAGE, SELECT ON SEQUENCE comex_gold_stock_id_seq TO economic;
