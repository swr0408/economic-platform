-- CFTC Legacy COT Positions (金融先物: FX, 株式指数, 債券, VIX)
-- DisAggコモディティはDisAggテーブルからLegacy相当値を算出するため不要
CREATE TABLE IF NOT EXISTS cftc_legacy_positions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    asset_code VARCHAR(10) NOT NULL,
    asset_name VARCHAR(50) NOT NULL,
    open_interest DOUBLE PRECISION,
    noncomm_long DOUBLE PRECISION,
    noncomm_short DOUBLE PRECISION,
    noncomm_spread DOUBLE PRECISION,
    noncomm_net DOUBLE PRECISION,
    comm_long DOUBLE PRECISION,
    comm_short DOUBLE PRECISION,
    comm_net DOUBLE PRECISION,
    nonrept_long DOUBLE PRECISION,
    nonrept_short DOUBLE PRECISION,
    nonrept_net DOUBLE PRECISION,
    source VARCHAR(50) DEFAULT 'CFTC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, asset_code)
);

CREATE INDEX IF NOT EXISTS idx_cftc_legacy_date ON cftc_legacy_positions(date);
CREATE INDEX IF NOT EXISTS idx_cftc_legacy_asset ON cftc_legacy_positions(asset_code);
CREATE INDEX IF NOT EXISTS idx_cftc_legacy_asset_date ON cftc_legacy_positions(asset_code, date);

GRANT ALL PRIVILEGES ON TABLE cftc_legacy_positions TO economic;
GRANT USAGE, SELECT ON SEQUENCE cftc_legacy_positions_id_seq TO economic;
