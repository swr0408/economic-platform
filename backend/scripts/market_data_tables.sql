-- =====================================================
-- 市場データテーブル作成
-- PostgreSQL + TimescaleDB
-- =====================================================

-- =====================================================
-- 1. 銘柄マスタ
-- =====================================================
CREATE TABLE IF NOT EXISTS public.market_symbols (
    id VARCHAR(50) PRIMARY KEY,              -- usdjpy, sp500, etc.
    ticker VARCHAR(50) NOT NULL,             -- yfinanceのティッカー (USDJPY=X, ^GSPC)
    name VARCHAR(100) NOT NULL,              -- 日本語名
    name_en VARCHAR(100) NOT NULL,           -- 英語名
    category VARCHAR(50) NOT NULL,           -- forex, index, commodity, bond
    sub_category VARCHAR(50),                -- forex_usd, index_us, etc.
    is_active BOOLEAN DEFAULT TRUE,

    -- 計算値用（例: gold_jpy = gold * usdjpy）
    is_calculated BOOLEAN DEFAULT FALSE,
    base_symbol_id VARCHAR(50) REFERENCES public.market_symbols(id),
    fx_symbol_id VARCHAR(50) REFERENCES public.market_symbols(id),
    operation VARCHAR(20),                   -- multiply, divide

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_market_symbols_category ON public.market_symbols (category);
CREATE INDEX IF NOT EXISTS idx_market_symbols_sub_category ON public.market_symbols (sub_category);

-- =====================================================
-- 2. 日足データ（TimescaleDBハイパーテーブル）
-- =====================================================
CREATE TABLE IF NOT EXISTS timeseries.market_daily_data (
    symbol_id VARCHAR(50) NOT NULL REFERENCES public.market_symbols(id),
    date DATE NOT NULL,
    open DECIMAL(18, 6),
    high DECIMAL(18, 6),
    low DECIMAL(18, 6),
    close DECIMAL(18, 6),
    volume BIGINT,
    source VARCHAR(50) DEFAULT 'yfinance',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_id, date)
);

-- TimescaleDBハイパーテーブル化
SELECT create_hypertable(
    'timeseries.market_daily_data',
    'date',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_market_daily_symbol ON timeseries.market_daily_data (symbol_id, date DESC);

-- =====================================================
-- 3. 分足データ（TimescaleDBハイパーテーブル）
-- =====================================================
CREATE TABLE IF NOT EXISTS timeseries.market_intraday_data (
    symbol_id VARCHAR(50) NOT NULL REFERENCES public.market_symbols(id),
    timestamp TIMESTAMPTZ NOT NULL,          -- UTC
    interval VARCHAR(10) NOT NULL,           -- '1m', '5m'
    open DECIMAL(18, 6),
    high DECIMAL(18, 6),
    low DECIMAL(18, 6),
    close DECIMAL(18, 6),
    volume BIGINT,
    source VARCHAR(50) DEFAULT 'yfinance',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_id, timestamp, interval)
);

-- TimescaleDBハイパーテーブル化（1週間ごとのチャンク）
SELECT create_hypertable(
    'timeseries.market_intraday_data',
    'timestamp',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_market_intraday_symbol ON timeseries.market_intraday_data (symbol_id, timestamp DESC, interval);

-- 圧縮ポリシー（7日後に自動圧縮）
ALTER TABLE timeseries.market_intraday_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol_id,interval'
);

SELECT add_compression_policy(
    'timeseries.market_intraday_data',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- =====================================================
-- 4. 指標発表日時マスタ
-- =====================================================
CREATE TABLE IF NOT EXISTS public.indicator_releases (
    id SERIAL PRIMARY KEY,
    indicator_id VARCHAR(100) NOT NULL,      -- ism_manufacturing, nonfarm_payrolls, etc.
    indicator_name VARCHAR(200) NOT NULL,    -- ISM製造業景況指数
    country VARCHAR(50) NOT NULL,            -- usa, japan, etc.

    -- 発表日時（UTC）
    release_datetime TIMESTAMPTZ NOT NULL,

    -- 発表値
    actual_value DECIMAL(18, 4),
    forecast_value DECIMAL(18, 4),
    previous_value DECIMAL(18, 4),

    -- メタデータ
    source VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (indicator_id, release_datetime)
);

CREATE INDEX IF NOT EXISTS idx_indicator_releases_datetime ON public.indicator_releases (release_datetime);
CREATE INDEX IF NOT EXISTS idx_indicator_releases_indicator ON public.indicator_releases (indicator_id, release_datetime DESC);

-- =====================================================
-- 5. 市場データ更新ログ
-- =====================================================
CREATE TABLE IF NOT EXISTS public.market_data_update_logs (
    id SERIAL PRIMARY KEY,
    symbol_id VARCHAR(50),                   -- NULL = 全銘柄
    data_type VARCHAR(20) NOT NULL,          -- daily, intraday_1m, intraday_5m

    -- 実行結果
    status VARCHAR(20) NOT NULL,             -- success, failed, partial
    records_updated INT DEFAULT 0,
    error_message TEXT,

    -- 実行時間
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_seconds DECIMAL(10, 3),

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_update_logs_started ON public.market_data_update_logs (started_at DESC);

-- =====================================================
-- 6. 銘柄マスタ初期データ投入
-- =====================================================

-- 為替（ドルストレート）
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('usdjpy', 'USDJPY=X', 'ドル円', 'USD/JPY', 'forex', 'forex_usd'),
('eurusd', 'EURUSD=X', 'ユーロドル', 'EUR/USD', 'forex', 'forex_usd'),
('gbpusd', 'GBPUSD=X', 'ポンドドル', 'GBP/USD', 'forex', 'forex_usd'),
('audusd', 'AUDUSD=X', '豪ドル米ドル', 'AUD/USD', 'forex', 'forex_usd'),
('nzdusd', 'NZDUSD=X', 'NZドル米ドル', 'NZD/USD', 'forex', 'forex_usd'),
('usdcad', 'USDCAD=X', 'ドルカナダ', 'USD/CAD', 'forex', 'forex_usd'),
('usdchf', 'USDCHF=X', 'ドルスイス', 'USD/CHF', 'forex', 'forex_usd')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    name = EXCLUDED.name,
    name_en = EXCLUDED.name_en,
    category = EXCLUDED.category,
    sub_category = EXCLUDED.sub_category,
    updated_at = CURRENT_TIMESTAMP;

-- 為替（クロス円）
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('eurjpy', 'EURJPY=X', 'ユーロ円', 'EUR/JPY', 'forex', 'forex_jpy'),
('gbpjpy', 'GBPJPY=X', 'ポンド円', 'GBP/JPY', 'forex', 'forex_jpy'),
('audjpy', 'AUDJPY=X', '豪ドル円', 'AUD/JPY', 'forex', 'forex_jpy'),
('nzdjpy', 'NZDJPY=X', 'NZドル円', 'NZD/JPY', 'forex', 'forex_jpy'),
('cadjpy', 'CADJPY=X', 'カナダ円', 'CAD/JPY', 'forex', 'forex_jpy'),
('chfjpy', 'CHFJPY=X', 'スイス円', 'CHF/JPY', 'forex', 'forex_jpy')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    name = EXCLUDED.name,
    updated_at = CURRENT_TIMESTAMP;

-- 為替（その他クロス）
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('eurgbp', 'EURGBP=X', 'ユーロポンド', 'EUR/GBP', 'forex', 'forex_cross'),
('euraud', 'EURAUD=X', 'ユーロ豪ドル', 'EUR/AUD', 'forex', 'forex_cross'),
('eurnzd', 'EURNZD=X', 'ユーロNZドル', 'EUR/NZD', 'forex', 'forex_cross'),
('eurcad', 'EURCAD=X', 'ユーロカナダ', 'EUR/CAD', 'forex', 'forex_cross'),
('eurchf', 'EURCHF=X', 'ユーロスイス', 'EUR/CHF', 'forex', 'forex_cross'),
('gbpaud', 'GBPAUD=X', 'ポンド豪ドル', 'GBP/AUD', 'forex', 'forex_cross'),
('gbpnzd', 'GBPNZD=X', 'ポンドNZドル', 'GBP/NZD', 'forex', 'forex_cross'),
('gbpcad', 'GBPCAD=X', 'ポンドカナダ', 'GBP/CAD', 'forex', 'forex_cross'),
('gbpchf', 'GBPCHF=X', 'ポンドスイス', 'GBP/CHF', 'forex', 'forex_cross'),
('audnzd', 'AUDNZD=X', '豪ドルNZドル', 'AUD/NZD', 'forex', 'forex_cross'),
('audcad', 'AUDCAD=X', '豪ドルカナダ', 'AUD/CAD', 'forex', 'forex_cross'),
('audchf', 'AUDCHF=X', '豪ドルスイス', 'AUD/CHF', 'forex', 'forex_cross'),
('nzdcad', 'NZDCAD=X', 'NZドルカナダ', 'NZD/CAD', 'forex', 'forex_cross'),
('nzdchf', 'NZDCHF=X', 'NZドルスイス', 'NZD/CHF', 'forex', 'forex_cross'),
('cadchf', 'CADCHF=X', 'カナダスイス', 'CAD/CHF', 'forex', 'forex_cross')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    updated_at = CURRENT_TIMESTAMP;

-- 通貨インデックス
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('dxy', 'DX-Y.NYB', 'ドルインデックス', 'USD Index (DXY)', 'forex', 'forex_index')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    updated_at = CURRENT_TIMESTAMP;

-- 米国株価指数
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('sp500', '^GSPC', 'S&P500', 'S&P 500', 'index', 'index_us'),
('dow', '^DJI', 'ダウ平均', 'Dow Jones', 'index', 'index_us'),
('nasdaq100', '^NDX', 'ナスダック100', 'Nasdaq 100', 'index', 'index_us'),
('nasdaq', '^IXIC', 'ナスダック総合', 'Nasdaq Composite', 'index', 'index_us'),
('russell2000', '^RUT', 'ラッセル2000', 'Russell 2000', 'index', 'index_us'),
('sox', '^SOX', 'フィラデルフィア半導体指数', 'SOX (Semiconductor)', 'index', 'index_us'),
('vix', '^VIX', 'VIX（恐怖指数）', 'VIX', 'index', 'index_us')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    updated_at = CURRENT_TIMESTAMP;

-- 日本・アジア株価指数
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('nikkei225', '^N225', '日経平均', 'Nikkei 225', 'index', 'index_asia'),
('topix', '^TOPX', 'TOPIX', 'TOPIX', 'index', 'index_asia'),
('hangseng', '^HSI', 'ハンセン指数', 'Hang Seng', 'index', 'index_asia')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    updated_at = CURRENT_TIMESTAMP;

-- 欧州株価指数
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('dax', '^GDAXI', 'DAX', 'DAX', 'index', 'index_europe'),
('ftse100', '^FTSE', 'FTSE100', 'FTSE 100', 'index', 'index_europe'),
('cac40', '^FCHI', 'CAC40', 'CAC 40', 'index', 'index_europe')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    updated_at = CURRENT_TIMESTAMP;

-- 債券利回り
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('us02y', '^IRX', '米国2年債利回り', 'US 2Y Yield', 'bond', 'bond'),
('us10y', '^TNX', '米国10年債利回り', 'US 10Y Yield', 'bond', 'bond'),
('us30y', '^TYX', '米国30年債利回り', 'US 30Y Yield', 'bond', 'bond')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    updated_at = CURRENT_TIMESTAMP;

-- 貴金属
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('gold', 'GC=F', '金（ドル建て）', 'Gold (USD)', 'commodity', 'commodity_metal'),
('silver', 'SI=F', '銀（ドル建て）', 'Silver (USD)', 'commodity', 'commodity_metal'),
('copper', 'HG=F', '銅', 'Copper', 'commodity', 'commodity_metal')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    updated_at = CURRENT_TIMESTAMP;

-- エネルギー
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category) VALUES
('crude_oil', 'CL=F', '原油（WTI）', 'Crude Oil (WTI)', 'commodity', 'commodity_energy'),
('brent_oil', 'BZ=F', '原油（ブレント）', 'Brent Crude', 'commodity', 'commodity_energy'),
('natural_gas', 'NG=F', '天然ガス', 'Natural Gas', 'commodity', 'commodity_energy')
ON CONFLICT (id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    updated_at = CURRENT_TIMESTAMP;

-- 計算値（株価指数系）
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category, is_calculated, base_symbol_id, fx_symbol_id, operation) VALUES
('nikkei_usd', '', '日経平均（ドル建て）', 'Nikkei 225 (USD)', 'index', 'calculated_index', TRUE, 'nikkei225', 'usdjpy', 'divide')
ON CONFLICT (id) DO UPDATE SET
    is_calculated = TRUE,
    base_symbol_id = 'nikkei225',
    fx_symbol_id = 'usdjpy',
    operation = 'divide',
    updated_at = CURRENT_TIMESTAMP;

-- 計算値（商品系）
INSERT INTO public.market_symbols (id, ticker, name, name_en, category, sub_category, is_calculated, base_symbol_id, fx_symbol_id, operation) VALUES
('gold_jpy', '', '金（円建て）', 'Gold (JPY)', 'commodity', 'calculated_commodity', TRUE, 'gold', 'usdjpy', 'multiply'),
('gold_eur', '', '金（ユーロ建て）', 'Gold (EUR)', 'commodity', 'calculated_commodity', TRUE, 'gold', 'eurusd', 'divide'),
('gold_gbp', '', '金（ポンド建て）', 'Gold (GBP)', 'commodity', 'calculated_commodity', TRUE, 'gold', 'gbpusd', 'divide'),
('gold_aud', '', '金（豪ドル建て）', 'Gold (AUD)', 'commodity', 'calculated_commodity', TRUE, 'gold', 'audusd', 'divide'),
('gold_cad', '', '金（カナダドル建て）', 'Gold (CAD)', 'commodity', 'calculated_commodity', TRUE, 'gold', 'usdcad', 'multiply'),
('gold_chf', '', '金（スイスフラン建て）', 'Gold (CHF)', 'commodity', 'calculated_commodity', TRUE, 'gold', 'usdchf', 'multiply'),
('gold_nzd', '', '金（NZドル建て）', 'Gold (NZD)', 'commodity', 'calculated_commodity', TRUE, 'gold', 'nzdusd', 'divide')
ON CONFLICT (id) DO UPDATE SET
    is_calculated = TRUE,
    base_symbol_id = EXCLUDED.base_symbol_id,
    fx_symbol_id = EXCLUDED.fx_symbol_id,
    operation = EXCLUDED.operation,
    updated_at = CURRENT_TIMESTAMP;

-- 完了メッセージ
DO $$
BEGIN
    RAISE NOTICE 'Market data tables created successfully!';
    RAISE NOTICE 'Symbols inserted: %', (SELECT COUNT(*) FROM public.market_symbols);
END $$;
