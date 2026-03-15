-- CFTC Disaggregated Positions (コモディティ: gold, silver, copper, crude_oil, brent, natural_gas)
CREATE TABLE IF NOT EXISTS cftc_disagg_positions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    asset_code VARCHAR(10) NOT NULL,
    asset_name VARCHAR(50) NOT NULL,
    open_interest DOUBLE PRECISION,
    mm_long DOUBLE PRECISION,
    mm_short DOUBLE PRECISION,
    mm_spread DOUBLE PRECISION,
    mm_net DOUBLE PRECISION,
    pm_long DOUBLE PRECISION,
    pm_short DOUBLE PRECISION,
    pm_net DOUBLE PRECISION,
    swap_long DOUBLE PRECISION,
    swap_short DOUBLE PRECISION,
    swap_spread DOUBLE PRECISION,
    swap_net DOUBLE PRECISION,
    other_long DOUBLE PRECISION,
    other_short DOUBLE PRECISION,
    other_spread DOUBLE PRECISION,
    other_net DOUBLE PRECISION,
    nonrept_long DOUBLE PRECISION,
    nonrept_short DOUBLE PRECISION,
    nonrept_net DOUBLE PRECISION,
    source VARCHAR(50) DEFAULT 'CFTC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, asset_code)
);

CREATE INDEX IF NOT EXISTS idx_cftc_disagg_date ON cftc_disagg_positions(date);
CREATE INDEX IF NOT EXISTS idx_cftc_disagg_asset ON cftc_disagg_positions(asset_code);
CREATE INDEX IF NOT EXISTS idx_cftc_disagg_asset_date ON cftc_disagg_positions(asset_code, date);

GRANT ALL PRIVILEGES ON TABLE cftc_disagg_positions TO economic;
GRANT USAGE, SELECT ON SEQUENCE cftc_disagg_positions_id_seq TO economic;


-- CFTC TFF Positions (金融先物: FX, 株式指数, 債券, VIX)
CREATE TABLE IF NOT EXISTS cftc_tff_positions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    asset_code VARCHAR(10) NOT NULL,
    asset_name VARCHAR(50) NOT NULL,
    open_interest DOUBLE PRECISION,
    dealer_long DOUBLE PRECISION,
    dealer_short DOUBLE PRECISION,
    dealer_spread DOUBLE PRECISION,
    dealer_net DOUBLE PRECISION,
    asset_mgr_long DOUBLE PRECISION,
    asset_mgr_short DOUBLE PRECISION,
    asset_mgr_spread DOUBLE PRECISION,
    asset_mgr_net DOUBLE PRECISION,
    lev_money_long DOUBLE PRECISION,
    lev_money_short DOUBLE PRECISION,
    lev_money_spread DOUBLE PRECISION,
    lev_money_net DOUBLE PRECISION,
    other_long DOUBLE PRECISION,
    other_short DOUBLE PRECISION,
    other_spread DOUBLE PRECISION,
    other_net DOUBLE PRECISION,
    nonrept_long DOUBLE PRECISION,
    nonrept_short DOUBLE PRECISION,
    nonrept_net DOUBLE PRECISION,
    source VARCHAR(50) DEFAULT 'CFTC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, asset_code)
);

CREATE INDEX IF NOT EXISTS idx_cftc_tff_date ON cftc_tff_positions(date);
CREATE INDEX IF NOT EXISTS idx_cftc_tff_asset ON cftc_tff_positions(asset_code);
CREATE INDEX IF NOT EXISTS idx_cftc_tff_asset_date ON cftc_tff_positions(asset_code, date);

GRANT ALL PRIVILEGES ON TABLE cftc_tff_positions TO economic;
GRANT USAGE, SELECT ON SEQUENCE cftc_tff_positions_id_seq TO economic;
