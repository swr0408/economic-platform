-- 日本小売業販売額の履歴データテーブル
-- 長期時系列データ + e-Stat速報データを格納

CREATE TABLE IF NOT EXISTS jp_retail_sales_history (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,           -- 対象年月（月初日）
    sales_amount DECIMAL(12, 1),         -- 販売額（10億円）
    yoy_change DECIMAL(6, 2),            -- 前年同月比（%）
    mom_change DECIMAL(6, 2),            -- 前月比（%）
    source VARCHAR(50) DEFAULT 'meti',   -- データソース（meti=経産省, fmp=FMP）
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_jp_retail_sales_history_date
ON jp_retail_sales_history(date);

-- 更新時のトリガー
CREATE OR REPLACE FUNCTION update_jp_retail_sales_history_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_jp_retail_sales_history_updated_at
ON jp_retail_sales_history;

CREATE TRIGGER trigger_jp_retail_sales_history_updated_at
BEFORE UPDATE ON jp_retail_sales_history
FOR EACH ROW
EXECUTE FUNCTION update_jp_retail_sales_history_updated_at();

-- 確認
SELECT 'Table jp_retail_sales_history created successfully' AS result;
