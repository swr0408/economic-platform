CREATE TABLE IF NOT EXISTS comex_silver_stock (
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
CREATE INDEX IF NOT EXISTS idx_comex_silver_stock_date ON comex_silver_stock(date);
