-- ドイツCPI/HICPの履歴データテーブル
-- Destatis GENESIS API（確報値）+ FMP（速報値）を統合格納

CREATE TABLE IF NOT EXISTS germany_cpi_history (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,              -- 対象年月（月初日）
    -- CPI (Consumer Price Index) - Table 61111-0002
    cpi_index DECIMAL(8, 2),                -- CPI指数値（2020=100）
    cpi_yoy_change DECIMAL(6, 2),           -- CPI前年比（%）
    cpi_mom_change DECIMAL(6, 2),           -- CPI前月比（%）
    -- HICP (Harmonised Index of Consumer Prices) - Table 61121-0002
    hicp_index DECIMAL(8, 2),               -- HICP指数値（2015=100）
    hicp_yoy_change DECIMAL(6, 2),          -- HICP前年比（%）
    hicp_mom_change DECIMAL(6, 2),          -- HICP前月比（%）
    -- メタデータ
    source VARCHAR(50) DEFAULT 'destatis',  -- データソース（destatis=確報, fmp=速報）
    is_preliminary BOOLEAN DEFAULT FALSE,   -- 速報値フラグ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_germany_cpi_history_date
ON germany_cpi_history(date);

CREATE INDEX IF NOT EXISTS idx_germany_cpi_history_source
ON germany_cpi_history(source);

-- 確認
SELECT 'Table germany_cpi_history created successfully' AS result;
