-- SHFE Copper Stock テーブル (単位: tonnes)
CREATE TABLE IF NOT EXISTS shfe_copper_stock (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    stock_tonnes DOUBLE PRECISION,
    source VARCHAR(50) DEFAULT 'SHFE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date)
);
CREATE INDEX IF NOT EXISTS idx_shfe_copper_stock_date ON shfe_copper_stock(date);

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE shfe_copper_stock TO economic;
GRANT USAGE, SELECT ON SEQUENCE shfe_copper_stock_id_seq TO economic;
