CREATE TABLE IF NOT EXISTS lme_copper_stock (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    cash_usd DOUBLE PRECISION,          -- LME Cash Settlement (USD/tonne)
    three_month_usd DOUBLE PRECISION,   -- LME 3-Month Forward (USD/tonne)
    stock_tonnes INTEGER,               -- Warehouse Stock (tonnes)
    source VARCHAR(50) DEFAULT 'LME',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date)
);

CREATE INDEX IF NOT EXISTS idx_lme_copper_stock_date ON lme_copper_stock(date);
