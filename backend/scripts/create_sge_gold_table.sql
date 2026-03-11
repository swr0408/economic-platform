-- SGE Au(T+D) 上海黄金取引所 日次取引データ
CREATE TABLE IF NOT EXISTS sge_au_td (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    open_price DOUBLE PRECISION,        -- 开盘价 (元/g)
    high_price DOUBLE PRECISION,        -- 最高价 (元/g)
    low_price DOUBLE PRECISION,         -- 最低价 (元/g)
    close_price DOUBLE PRECISION,       -- 收盘价 (元/g)
    settlement_price DOUBLE PRECISION,  -- 加权平均价 (元/g)
    volume_kg DOUBLE PRECISION,         -- 成交量 (kg)
    amount_cny DOUBLE PRECISION,        -- 成交金额 (元)
    open_interest INTEGER,              -- 市場持仓 (手)
    source VARCHAR(50) DEFAULT 'SGE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sge_au_td_date ON sge_au_td(date);
