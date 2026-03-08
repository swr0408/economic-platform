-- 中国国債発行（Government Bond Issuance）テーブル
-- データソース: 中国財政部 https://zwgls.mof.gov.cn/ywgg/

-- 通知テーブル（入札予定）
CREATE TABLE IF NOT EXISTS mof_bond_notices (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    publish_date DATE NOT NULL,
    title TEXT NOT NULL,
    bond_name TEXT,
    bond_type TEXT,
    is_reissue BOOLEAN DEFAULT FALSE,
    maturity_years NUMERIC,
    maturity_days INTEGER,
    issue_amount NUMERIC,
    bidding_date DATE,
    bidding_time_start TEXT,
    bidding_time_end TEXT,
    bidding_method TEXT,
    interest_start_date DATE,
    redemption_date DATE,
    listing_date DATE,
    coupon_frequency TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 公告テーブル（入札結果）
CREATE TABLE IF NOT EXISTS mof_bond_results (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    publish_date DATE NOT NULL,
    title TEXT NOT NULL,
    notice_number TEXT,
    bond_name TEXT,
    bond_type TEXT,
    is_reissue BOOLEAN DEFAULT FALSE,
    maturity_years NUMERIC,
    maturity_days INTEGER,
    planned_amount NUMERIC,
    actual_amount NUMERIC,
    issue_price NUMERIC,
    annual_yield NUMERIC,
    coupon_rate NUMERIC,
    interest_start_date DATE,
    redemption_date DATE,
    listing_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mof_bond_notices_publish_date ON mof_bond_notices(publish_date DESC);
CREATE INDEX IF NOT EXISTS idx_mof_bond_results_publish_date ON mof_bond_results(publish_date DESC);
CREATE INDEX IF NOT EXISTS idx_mof_bond_notices_bidding_date ON mof_bond_notices(bidding_date);
