-- NBS (National Bureau of Statistics) 月次データ蓄積テーブル
-- 中国のNBS統計データAPIから取得したデータを永続化
--
-- 対象指標:
-- - cn_ppi_yoy: PPI前年比 (A01080101)
-- - cn_ppi_mom: PPI前月比 (A01080701)
-- - cn_unemployment_total: 全国城鎮調査失業率 (A0E0101)
-- - cn_unemployment_youth: 16-24歳若年層失業率 (A0E0105)
-- - cn_re_floor_started_yoy: 商品住宅新規着工面積 累計YoY (A060504)
-- - cn_re_sales_yoy: 商品房販売額 累計YoY (A060902)
-- - cn_re_floor_sold_yoy: 商品房販売面積 累計YoY (A060802)

CREATE TABLE IF NOT EXISTS nbs_monthly_data (
    indicator VARCHAR(64) NOT NULL,
    date DATE NOT NULL,
    value DECIMAL(20, 4) NOT NULL,
    source VARCHAR(16) NOT NULL DEFAULT 'api',  -- 'csv' or 'api'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (indicator, date)
);

CREATE INDEX IF NOT EXISTS idx_nbs_monthly_indicator ON nbs_monthly_data (indicator);
CREATE INDEX IF NOT EXISTS idx_nbs_monthly_date ON nbs_monthly_data (date);
