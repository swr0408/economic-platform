-- スペインCPI/HICPの履歴データテーブル
-- INE (Instituto Nacional de Estadística) から取得

CREATE TABLE IF NOT EXISTS spain_cpi_history (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,              -- 対象年月（月初日）
    -- CPI (Consumer Price Index) - IPC
    cpi_yoy DECIMAL(6, 2),                  -- CPI前年比（%）IPC251856
    cpi_mom DECIMAL(6, 2),                  -- CPI前月比（%）IPC251855
    -- Core CPI (Underlying Inflation) - 食料・エネルギー除く
    core_cpi_yoy DECIMAL(6, 2),             -- コアCPI前年比（%）IPC253990
    core_cpi_mom DECIMAL(6, 2),             -- コアCPI前月比（%）IPC253989
    -- HICP (Harmonised Index of Consumer Prices) - IPCA
    hicp_yoy DECIMAL(6, 2),                 -- HICP前年比（%）IPCA1885
    hicp_mom DECIMAL(6, 2),                 -- HICP前月比（%）IPCA1886
    -- メタデータ
    source VARCHAR(50) DEFAULT 'ine_api',   -- データソース（ine_csv=初回CSV, ine_api=API更新）
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_spain_cpi_history_date
ON spain_cpi_history(date);

CREATE INDEX IF NOT EXISTS idx_spain_cpi_history_source
ON spain_cpi_history(source);

-- 確認
SELECT 'Table spain_cpi_history created successfully' AS result;
