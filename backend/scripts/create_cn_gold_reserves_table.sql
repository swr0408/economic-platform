-- 中国人民銀行 金準備 (Official Reserve Assets - Gold) 月次データ
-- ソース: PBOC / SAFE
CREATE TABLE IF NOT EXISTS cn_gold_reserves (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    gold_ounces_wan DOUBLE PRECISION,       -- 金準備（万盎司 = 万トロイオンス）
    gold_value_usd_yi DOUBLE PRECISION,     -- 金評価額（亿美元 = 億USD）※2016年4月以降
    source VARCHAR(50) DEFAULT 'PBOC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cn_gold_reserves_date ON cn_gold_reserves(date);
