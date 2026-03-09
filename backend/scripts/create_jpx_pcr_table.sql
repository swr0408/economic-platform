-- JPX 日本株指数オプション Put/Call Ratio テーブル
-- 日経225オプション、日経225ミニオプション、TOPIXオプション

CREATE TABLE IF NOT EXISTS jpx_put_call_ratio (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    product VARCHAR(30) NOT NULL,  -- 'nikkei225', 'nikkei225_mini', 'topix'
    put_volume BIGINT,
    call_volume BIGINT,
    put_oi BIGINT,
    call_oi BIGINT,
    volume_pcr NUMERIC(10, 4),     -- put_volume / call_volume
    oi_pcr NUMERIC(10, 4),         -- put_oi / call_oi
    source VARCHAR(50) DEFAULT 'JPX',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT jpx_pcr_date_product_unique UNIQUE (date, product)
);

CREATE INDEX IF NOT EXISTS idx_jpx_pcr_date
ON jpx_put_call_ratio (date DESC);

CREATE INDEX IF NOT EXISTS idx_jpx_pcr_product_date
ON jpx_put_call_ratio (product, date DESC);
