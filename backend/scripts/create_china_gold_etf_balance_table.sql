-- 中国金ETF残高 (518880 華安黄金ETF) 日次 総份額データ
-- ソース: 上海証券交易所 (SSE)
CREATE TABLE IF NOT EXISTS china_gold_etf_balance (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    fund_code VARCHAR(10) NOT NULL DEFAULT '518880',
    total_shares_wan DOUBLE PRECISION,  -- 総份額（万份）
    source VARCHAR(50) DEFAULT 'SSE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_china_gold_etf_balance_date ON china_gold_etf_balance(date);
