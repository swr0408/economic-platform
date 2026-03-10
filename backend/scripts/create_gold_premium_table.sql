CREATE TABLE IF NOT EXISTS gold_premium (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    china DOUBLE PRECISION,          -- 中国プレミアム/ディスカウント (US$/oz, 5日移動平均)
    india DOUBLE PRECISION,          -- インドプレミアム/ディスカウント (US$/oz, 5日移動平均)
    source VARCHAR(20) DEFAULT 'WGC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date)
);

CREATE INDEX IF NOT EXISTS idx_gold_premium_date ON gold_premium(date);
