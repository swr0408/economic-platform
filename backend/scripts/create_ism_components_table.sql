-- ISM Components（製造業・非製造業）サブインデックス蓄積テーブル
-- DBnomics APIから取得した過去データを永続化し、API障害時のフォールバックに使用
--
-- 対象:
-- - manufacturing: ISM製造業構成指数（new_orders, production, employment, supplier_deliveries, prices, inventories）
-- - non_manufacturing: ISM非製造業構成指数（new_orders, business_activity, employment, supplier_deliveries, prices, inventories）

CREATE TABLE IF NOT EXISTS ism_components (
    type VARCHAR(20) NOT NULL,              -- 'manufacturing' or 'non_manufacturing'
    date DATE NOT NULL,
    new_orders DECIMAL(5,1),
    production DECIMAL(5,1),                -- 製造業のみ（非製造業はNULL）
    business_activity DECIMAL(5,1),         -- 非製造業のみ（製造業はNULL）
    employment DECIMAL(5,1),
    supplier_deliveries DECIMAL(5,1),
    prices DECIMAL(5,1),
    inventories DECIMAL(5,1),
    source VARCHAR(16) NOT NULL DEFAULT 'dbnomics',  -- 'dbnomics', 'csv', 'fmp'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (type, date)
);

CREATE INDEX IF NOT EXISTS idx_ism_components_type ON ism_components (type);
CREATE INDEX IF NOT EXISTS idx_ism_components_date ON ism_components (date);
