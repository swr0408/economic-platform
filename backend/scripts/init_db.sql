-- TimescaleDB拡張を有効化
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- スキーマ作成
CREATE SCHEMA IF NOT EXISTS timeseries;

-- 経済指標マスターテーブル
CREATE TABLE IF NOT EXISTS public.economic_indicators (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    name_en VARCHAR(255),
    name_ja VARCHAR(255),
    country VARCHAR(10) NOT NULL,
    category VARCHAR(100),
    subcategory VARCHAR(100),
    unit VARCHAR(50),
    frequency VARCHAR(20),
    source VARCHAR(100),
    source_url TEXT,
    description TEXT,
    importance INT CHECK (importance BETWEEN 1 AND 5),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_indicators_country ON public.economic_indicators (country);
CREATE INDEX IF NOT EXISTS idx_indicators_category ON public.economic_indicators (category);
CREATE INDEX IF NOT EXISTS idx_indicators_code ON public.economic_indicators (code);

-- 経済指標データ（時系列）
CREATE TABLE IF NOT EXISTS timeseries.economic_data (
    indicator_id INT NOT NULL REFERENCES public.economic_indicators(id),
    timestamp TIMESTAMPTZ NOT NULL,
    value DECIMAL(20, 4),
    value_original DECIMAL(20, 4),
    unit VARCHAR(50),
    period VARCHAR(20),
    is_preliminary BOOLEAN DEFAULT FALSE,
    is_revised BOOLEAN DEFAULT FALSE,
    revision_number INT DEFAULT 0,
    metadata JSONB,
    source_update_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (indicator_id, timestamp)
);

-- TimescaleDBハイパーテーブル化
SELECT create_hypertable('timeseries.economic_data', 'timestamp',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_economic_data_indicator ON timeseries.economic_data (indicator_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_economic_data_period ON timeseries.economic_data (period);

-- =====================================================
-- 経済指標マスターデータ登録
-- 新しい指標を追加する場合はここにINSERTを追加
-- =====================================================

-- USA (アメリカ)
INSERT INTO public.economic_indicators (code, name, name_en, name_ja, country, category, subcategory, unit, frequency, source, importance)
VALUES (
    'US_POLICY_RATE',
    'Federal Funds Target Rate',
    'Federal Funds Target Rate',
    '連邦準備制度政策金利',
    'USA',
    'monetary_policy',
    'interest_rate',
    '%',
    'weekly',
    'Federal Reserve H.15',
    5
) ON CONFLICT (code) DO NOTHING;

-- USA CPI (将来追加用テンプレート)
-- INSERT INTO public.economic_indicators (code, name, name_en, name_ja, country, category, subcategory, unit, frequency, source, importance)
-- VALUES (
--     'US_CPI',
--     'Consumer Price Index',
--     'Consumer Price Index',
--     '消費者物価指数',
--     'USA',
--     'inflation',
--     'cpi',
--     'index',
--     'monthly',
--     'BLS',
--     5
-- ) ON CONFLICT (code) DO NOTHING;

-- JAPAN (日本)
INSERT INTO public.economic_indicators (code, name, name_en, name_ja, country, category, subcategory, unit, frequency, source, importance)
VALUES (
    'JP_CPI',
    'Japan Consumer Price Index',
    'Japan Consumer Price Index',
    '消費者物価指数',
    'JPN',
    'inflation',
    'cpi',
    'index',
    'monthly',
    'e-Stat',
    5
) ON CONFLICT (code) DO NOTHING;

-- JP_POLICY_RATE (日銀政策金利)
INSERT INTO public.economic_indicators (code, name, name_en, name_ja, country, category, subcategory, unit, frequency, source, importance)
VALUES (
    'JP_POLICY_RATE',
    'BOJ Policy Rate',
    'Bank of Japan Policy Rate',
    '日本銀行政策金利',
    'JPN',
    'monetary_policy',
    'interest_rate',
    '%',
    'monthly',
    'BOJ',
    5
) ON CONFLICT (code) DO NOTHING;

-- 圧縮ポリシー（30日後に自動圧縮）
ALTER TABLE timeseries.economic_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'indicator_id'
);

SELECT add_compression_policy('timeseries.economic_data', INTERVAL '30 days', if_not_exists => TRUE);
