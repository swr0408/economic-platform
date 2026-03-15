-- COMEX Copper Stock テーブル (単位: short tons)
CREATE TABLE IF NOT EXISTS comex_copper_stock (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    registered_tons DOUBLE PRECISION,
    eligible_tons DOUBLE PRECISION,
    total_tons DOUBLE PRECISION,
    source VARCHAR(50) DEFAULT 'CME',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date)
);
CREATE INDEX IF NOT EXISTS idx_comex_copper_stock_date ON comex_copper_stock(date);

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE comex_copper_stock TO economic;
GRANT USAGE, SELECT ON SEQUENCE comex_copper_stock_id_seq TO economic;
