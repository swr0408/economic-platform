-- 日本 所定内給与 履歴テーブル
-- e-Stat 毎月勤労統計調査からの長期時系列データを格納

-- テーブル作成
CREATE TABLE IF NOT EXISTS japan_scheduled_wage_history (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,

    -- 所定内給与（就業形態計）
    scheduled_wage_index NUMERIC(10, 2),      -- 賃金指数
    scheduled_wage_yoy NUMERIC(10, 2),        -- 前年比（%）

    -- 一般労働者
    general_index NUMERIC(10, 2),             -- 賃金指数
    general_yoy NUMERIC(10, 2),               -- 前年比（%）

    -- パートタイム労働者
    part_time_index NUMERIC(10, 2),           -- 賃金指数
    part_time_yoy NUMERIC(10, 2),             -- 前年比（%）

    -- メタデータ
    source VARCHAR(50) DEFAULT 'e-Stat',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT japan_scheduled_wage_history_date_unique UNIQUE (date)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_japan_scheduled_wage_history_date
ON japan_scheduled_wage_history (date DESC);

-- コメント
COMMENT ON TABLE japan_scheduled_wage_history IS '日本 所定内給与 履歴データ（毎月勤労統計調査）';
COMMENT ON COLUMN japan_scheduled_wage_history.scheduled_wage_index IS '所定内給与 賃金指数（基準年=100）';
COMMENT ON COLUMN japan_scheduled_wage_history.scheduled_wage_yoy IS '所定内給与 前年同月比（%）';
COMMENT ON COLUMN japan_scheduled_wage_history.general_index IS '一般労働者 賃金指数';
COMMENT ON COLUMN japan_scheduled_wage_history.general_yoy IS '一般労働者 前年同月比（%）';
COMMENT ON COLUMN japan_scheduled_wage_history.part_time_index IS 'パートタイム労働者 賃金指数';
COMMENT ON COLUMN japan_scheduled_wage_history.part_time_yoy IS 'パートタイム労働者 前年同月比（%）';
