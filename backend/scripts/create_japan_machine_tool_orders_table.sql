-- Japan Machine Tool Orders History Table
-- Stores historical data imported from JMTBA PDF archives

-- Create table
CREATE TABLE IF NOT EXISTS japan_machine_tool_orders_history (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,

    -- Order amounts (million yen)
    total_orders NUMERIC(12, 0),
    domestic_orders NUMERIC(12, 0),
    foreign_orders NUMERIC(12, 0),

    -- YoY change (%)
    total_yoy NUMERIC(10, 2),
    domestic_yoy NUMERIC(10, 2),
    foreign_yoy NUMERIC(10, 2),

    -- Metadata
    source VARCHAR(50) DEFAULT 'JMTBA',
    data_type VARCHAR(20) DEFAULT 'kakuhou',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT japan_machine_tool_orders_history_date_unique UNIQUE (date)
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_japan_machine_tool_orders_history_date
ON japan_machine_tool_orders_history (date DESC);

-- Comments
COMMENT ON TABLE japan_machine_tool_orders_history IS 'Japan Machine Tool Orders History (JMTBA)';
COMMENT ON COLUMN japan_machine_tool_orders_history.total_orders IS 'Total orders (million yen)';
COMMENT ON COLUMN japan_machine_tool_orders_history.domestic_orders IS 'Domestic orders (million yen)';
COMMENT ON COLUMN japan_machine_tool_orders_history.foreign_orders IS 'Foreign orders (million yen)';
COMMENT ON COLUMN japan_machine_tool_orders_history.total_yoy IS 'Total orders YoY change (%)';
COMMENT ON COLUMN japan_machine_tool_orders_history.domestic_yoy IS 'Domestic orders YoY change (%)';
COMMENT ON COLUMN japan_machine_tool_orders_history.foreign_yoy IS 'Foreign orders YoY change (%)';
COMMENT ON COLUMN japan_machine_tool_orders_history.data_type IS 'Data type (kakuhou: confirmed, sokuhou: preliminary)';
