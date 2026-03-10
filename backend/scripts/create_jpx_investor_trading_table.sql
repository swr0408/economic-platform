-- 投資部門別売買状況テーブル
-- JPX XLSファイルから週次ネット売買金額を蓄積
-- 単位: 千円

CREATE TABLE IF NOT EXISTS jpx_investor_trading (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,                  -- 週の開始日
    individuals BIGINT,                  -- 個人（千円）
    foreigners BIGINT,                   -- 海外投資家（千円）
    trust_banks BIGINT,                  -- 信託銀行（千円）
    investment_trusts BIGINT,            -- 投資信託（千円）
    business_corps BIGINT,              -- 事業法人（千円）
    proprietary BIGINT,                  -- 自己計（千円）
    source VARCHAR(50) DEFAULT 'XLS',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date)
);

CREATE INDEX IF NOT EXISTS idx_jpx_investor_trading_date ON jpx_investor_trading(date);
