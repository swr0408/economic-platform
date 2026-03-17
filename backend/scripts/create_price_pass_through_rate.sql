-- 価格転嫁率テーブル作成DDL

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TABLE IF NOT EXISTS price_pass_through_rate (
    id                  SERIAL PRIMARY KEY,
    survey_date         DATE NOT NULL UNIQUE,
    survey_period       TEXT NOT NULL,
    total               NUMERIC(5,1) NOT NULL,
    raw_materials       NUMERIC(5,1),
    energy              NUMERIC(5,1),
    labor               NUMERIC(5,1),
    zero_pass_through   NUMERIC(5,1),
    supply_chain        JSONB,
    source              TEXT NOT NULL DEFAULT 'hardcoded',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_price_pass_through_rate_date
ON price_pass_through_rate(survey_date DESC);

DROP TRIGGER IF EXISTS update_price_pass_through_rate_updated_at ON price_pass_through_rate;
CREATE TRIGGER update_price_pass_through_rate_updated_at
    BEFORE UPDATE ON price_pass_through_rate
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
