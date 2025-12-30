-- ============================================================================
-- 経済指標カレンダー テーブル定義
-- FMPからの発表スケジュールデータを格納
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. 生データ格納テーブル（FMPイベント）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS economic_calendar_events (
    id              BIGSERIAL PRIMARY KEY,
    provider        TEXT NOT NULL DEFAULT 'FMP',
    event_key       TEXT NOT NULL,                  -- hash(provider,country,event,datetime_raw)
    country         TEXT,                           -- 国コード (US, JP, DE, GB, etc.)
    currency        TEXT,                           -- 通貨コード (USD, JPY, etc.)
    event           TEXT NOT NULL,                  -- FMPのイベント名
    event_period    TEXT,                           -- 抽出した期間情報 (Nov, Q3, Dec/19 etc.)
    datetime_raw    TEXT NOT NULL,                  -- FMPが返した日時文字列
    datetime_utc    TIMESTAMPTZ,                    -- UTC正規化した日時
    has_time        BOOLEAN NOT NULL DEFAULT TRUE,  -- 時刻あり/なし判定
    impact          TEXT,                           -- Low/Medium/High
    previous        NUMERIC(20, 6),                 -- 前回値
    estimate        NUMERIC(20, 6),                 -- 予想値
    actual          NUMERIC(20, 6),                 -- 実績値
    change          NUMERIC(20, 6),                 -- 変化量
    change_pct      NUMERIC(10, 4),                 -- 変化率
    unit            TEXT,                           -- 単位 (%, K, M, B等)
    raw_json        JSONB NOT NULL,                 -- 元のレスポンスを丸ごと保存
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ユニーク制約（重複防止）
CREATE UNIQUE INDEX IF NOT EXISTS uq_economic_calendar_events_key
ON economic_calendar_events(provider, event_key);

-- 検索用インデックス
CREATE INDEX IF NOT EXISTS ix_economic_calendar_events_country_dt
ON economic_calendar_events(country, datetime_utc);

CREATE INDEX IF NOT EXISTS ix_economic_calendar_events_event
ON economic_calendar_events(event);

CREATE INDEX IF NOT EXISTS ix_economic_calendar_events_datetime
ON economic_calendar_events(datetime_utc DESC);

-- ----------------------------------------------------------------------------
-- 2. 同期状態管理テーブル
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS provider_sync_state (
    provider        TEXT PRIMARY KEY,
    last_success_at TIMESTAMPTZ,
    last_range_from DATE,
    last_range_to   DATE,
    records_count   INTEGER DEFAULT 0,
    last_error      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 3. 指標候補テーブル（国別イベント集計）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS economic_indicator_candidates (
    id                  SERIAL PRIMARY KEY,
    provider            TEXT NOT NULL DEFAULT 'FMP',
    country             TEXT NOT NULL,
    event               TEXT NOT NULL,              -- 表示用（代表文字列）
    event_norm          TEXT NOT NULL,              -- 正規化したevent
    occurrences_1y      INTEGER NOT NULL DEFAULT 0, -- 過去1年の出現回数
    first_seen_utc      TIMESTAMPTZ,
    last_seen_utc       TIMESTAMPTZ,
    typical_weekday     INTEGER,                    -- 最頻曜日 0=Mon..6=Sun
    typical_hour_utc    INTEGER,                    -- 最頻時間 0..23
    has_time_ratio      NUMERIC(5, 2),              -- 時刻付き比率
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(provider, country, event_norm)
);

CREATE INDEX IF NOT EXISTS ix_indicator_candidates_country
ON economic_indicator_candidates(country);

-- ----------------------------------------------------------------------------
-- 4. EconAlpha指標マッピングテーブル
-- FMPイベント名 → EconAlpha指標ID の紐付け
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS indicator_event_mapping (
    id                  SERIAL PRIMARY KEY,
    econalpha_id        TEXT NOT NULL,              -- EconAlphaの指標ID (ism_manufacturing等)
    econalpha_name      TEXT NOT NULL,              -- 表示名
    country             TEXT NOT NULL,              -- 国コード
    frequency           TEXT NOT NULL,              -- monthly, quarterly, weekly等
    fmp_event_patterns  TEXT[] NOT NULL,            -- FMPイベント名パターン（複数対応）
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(econalpha_id)
);

CREATE INDEX IF NOT EXISTS ix_indicator_mapping_country
ON indicator_event_mapping(country);

-- ----------------------------------------------------------------------------
-- 5. 指標発表履歴テーブル（EconAlphaIDと紐付け済み）
-- 1分足・5分足表示用の正規化済みデータ
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS indicator_releases (
    id                  BIGSERIAL PRIMARY KEY,
    econalpha_id        TEXT NOT NULL,              -- EconAlphaの指標ID
    release_datetime    TIMESTAMPTZ NOT NULL,       -- 発表日時（UTC）
    release_date        DATE NOT NULL,              -- 発表日（検索用）
    period_label        TEXT,                       -- 対象期間 (Nov 2024, Q3 2024等)
    previous            NUMERIC(20, 6),
    estimate            NUMERIC(20, 6),
    actual              NUMERIC(20, 6),
    surprise            NUMERIC(20, 6),             -- actual - estimate
    surprise_pct        NUMERIC(10, 4),             -- サプライズ率
    impact              TEXT,
    source_event_id     BIGINT REFERENCES economic_calendar_events(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(econalpha_id, release_datetime)
);

CREATE INDEX IF NOT EXISTS ix_indicator_releases_id_date
ON indicator_releases(econalpha_id, release_date DESC);

CREATE INDEX IF NOT EXISTS ix_indicator_releases_datetime
ON indicator_releases(release_datetime DESC);

-- ----------------------------------------------------------------------------
-- 更新トリガー
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_economic_calendar_events_updated_at ON economic_calendar_events;
CREATE TRIGGER update_economic_calendar_events_updated_at
    BEFORE UPDATE ON economic_calendar_events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_provider_sync_state_updated_at ON provider_sync_state;
CREATE TRIGGER update_provider_sync_state_updated_at
    BEFORE UPDATE ON provider_sync_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_indicator_candidates_updated_at ON economic_indicator_candidates;
CREATE TRIGGER update_indicator_candidates_updated_at
    BEFORE UPDATE ON economic_indicator_candidates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_indicator_mapping_updated_at ON indicator_event_mapping;
CREATE TRIGGER update_indicator_mapping_updated_at
    BEFORE UPDATE ON indicator_event_mapping
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 初期データ: 主要指標のマッピング（US）
-- ----------------------------------------------------------------------------
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    -- 経済 - 景況感
    ('ism_manufacturing', 'ISM製造業景況指数', 'US', 'monthly',
     ARRAY['ISM Manufacturing PMI']),
    ('ism_non_manufacturing', 'ISM非製造業景況指数', 'US', 'monthly',
     ARRAY['ISM Non-Manufacturing PMI', 'ISM Services PMI']),
    ('empire_state', 'NY連銀製造業景気指数', 'US', 'monthly',
     ARRAY['NY Empire State Manufacturing Index']),
    ('philadelphia_fed', 'フィラデルフィア連銀製造業景気指数', 'US', 'monthly',
     ARRAY['Philadelphia Fed Manufacturing Index']),
    ('nfib', 'NFIB中小企業楽観指数', 'US', 'monthly',
     ARRAY['NFIB Business Optimism Index']),

    -- 経済 - 生産
    ('industrial_production', '鉱工業生産', 'US', 'monthly',
     ARRAY['Industrial Production MoM', 'Industrial Production YoY']),
    ('capacity_utilization', '設備稼働率', 'US', 'monthly',
     ARRAY['Capacity Utilization']),
    ('durable_goods', '耐久財受注', 'US', 'monthly',
     ARRAY['Durable Goods Orders', 'Durable Goods Orders MoM']),

    -- 雇用
    ('unemployment_rate', '失業率', 'US', 'monthly',
     ARRAY['Unemployment Rate']),
    ('nonfarm_payrolls', '非農業部門雇用者数', 'US', 'monthly',
     ARRAY['Nonfarm Payrolls', 'Non Farm Payrolls']),
    ('adp_employment', 'ADP雇用統計', 'US', 'monthly',
     ARRAY['ADP Employment Change']),
    ('initial_claims', '新規失業保険申請件数', 'US', 'weekly',
     ARRAY['Initial Jobless Claims']),
    ('continued_claims', '継続受給者数', 'US', 'weekly',
     ARRAY['Continuing Jobless Claims']),
    ('jolts_openings', 'JOLTS求人件数', 'US', 'monthly',
     ARRAY['JOLTs Job Openings']),
    ('average_hourly_earnings', '平均時給', 'US', 'monthly',
     ARRAY['Average Hourly Earnings MoM', 'Average Hourly Earnings YoY']),
    ('employment_cost_index', '雇用コスト指数', 'US', 'quarterly',
     ARRAY['Employment Cost Index QoQ']),
    ('unit_labor_cost', '単位労働コスト', 'US', 'quarterly',
     ARRAY['Unit Labour Costs QoQ']),

    -- 消費
    ('retail_sales', '小売売上高', 'US', 'monthly',
     ARRAY['Retail Sales MoM', 'Retail Sales YoY', 'Core Retail Sales MoM']),
    ('pce', '個人消費支出', 'US', 'monthly',
     ARRAY['PCE Price Index MoM', 'PCE Price Index YoY', 'Core PCE Price Index MoM', 'Core PCE Price Index YoY']),
    ('personal_income', '個人所得', 'US', 'monthly',
     ARRAY['Personal Income MoM']),
    ('personal_spending', '個人支出', 'US', 'monthly',
     ARRAY['Personal Spending MoM']),
    ('cb_consumer_confidence', 'CB消費者信頼感指数', 'US', 'monthly',
     ARRAY['CB Consumer Confidence']),
    ('michigan_consumer_sentiment', 'ミシガン大学消費者信頼感指数', 'US', 'monthly',
     ARRAY['Michigan Consumer Sentiment', 'Michigan Consumer Expectations']),

    -- GDP
    ('gdp_growth', 'GDP成長率', 'US', 'quarterly',
     ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate']),

    -- インフレ
    ('cpi', '消費者物価指数', 'US', 'monthly',
     ARRAY['CPI', 'CPI MoM', 'CPI YoY', 'Core CPI MoM', 'Core CPI YoY']),
    ('ppi', '生産者物価指数', 'US', 'monthly',
     ARRAY['PPI MoM', 'PPI YoY', 'Core PPI MoM', 'Core PPI YoY']),

    -- 住宅
    ('housing_starts', '住宅着工件数', 'US', 'monthly',
     ARRAY['Housing Starts', 'Housing Starts MoM']),
    ('building_permits', '建設許可件数', 'US', 'monthly',
     ARRAY['Building Permits', 'Building Permits MoM']),
    ('existing_home_sales', '中古住宅販売件数', 'US', 'monthly',
     ARRAY['Existing Home Sales', 'Existing Home Sales MoM']),
    ('new_home_sales', '新築住宅販売件数', 'US', 'monthly',
     ARRAY['New Home Sales', 'New Home Sales MoM']),

    -- 金融政策
    ('fed_rate', 'FRB政策金利', 'US', 'irregular',
     ARRAY['Fed Interest Rate Decision'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- 日本の主要指標マッピング
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('jp_gdp', 'GDP成長率', 'JP', 'quarterly',
     ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY']),
    ('jp_cpi', '消費者物価指数', 'JP', 'monthly',
     ARRAY['CPI', 'CPI YoY', 'Core CPI YoY']),
    ('jp_tankan', '日銀短観', 'JP', 'quarterly',
     ARRAY['Tankan Large Manufacturers Index', 'Tankan Non-Manufacturing Index']),
    ('jp_industrial_production', '鉱工業生産', 'JP', 'monthly',
     ARRAY['Industrial Production MoM', 'Industrial Production YoY']),
    ('jp_unemployment', '失業率', 'JP', 'monthly',
     ARRAY['Unemployment Rate']),
    ('jp_boj_rate', '日銀政策金利', 'JP', 'irregular',
     ARRAY['BoJ Interest Rate Decision'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

-- ユーロ圏の主要指標マッピング
INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns)
VALUES
    ('eu_gdp', 'GDP成長率', 'EU', 'quarterly',
     ARRAY['GDP Growth Rate QoQ', 'GDP Growth Rate YoY']),
    ('eu_cpi', '消費者物価指数', 'EU', 'monthly',
     ARRAY['CPI', 'CPI YoY', 'Core CPI YoY', 'HICP YoY']),
    ('eu_pmi_manufacturing', '製造業PMI', 'EU', 'monthly',
     ARRAY['Manufacturing PMI']),
    ('eu_pmi_services', 'サービス業PMI', 'EU', 'monthly',
     ARRAY['Services PMI']),
    ('eu_unemployment', '失業率', 'EU', 'monthly',
     ARRAY['Unemployment Rate']),
    ('eu_ecb_rate', 'ECB政策金利', 'EU', 'irregular',
     ARRAY['ECB Interest Rate Decision', 'ECB Deposit Facility Rate'])
ON CONFLICT (econalpha_id) DO UPDATE SET
    fmp_event_patterns = EXCLUDED.fmp_event_patterns,
    updated_at = NOW();

COMMENT ON TABLE economic_calendar_events IS 'FMPから取得した経済指標イベントの生データ';
COMMENT ON TABLE provider_sync_state IS 'データプロバイダーとの同期状態管理';
COMMENT ON TABLE economic_indicator_candidates IS '国別イベントの集計結果（指標候補一覧）';
COMMENT ON TABLE indicator_event_mapping IS 'EconAlpha指標IDとFMPイベント名の紐付け';
COMMENT ON TABLE indicator_releases IS '正規化済みの指標発表履歴（1分足/5分足表示用）';
