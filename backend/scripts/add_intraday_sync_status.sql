-- =====================================================
-- 分足データ同期状態管理テーブル
-- 銘柄×足種ごとの最終同期日時を管理
-- =====================================================

-- 同期状態テーブル
CREATE TABLE IF NOT EXISTS public.market_intraday_sync_status (
    symbol_id VARCHAR(50) NOT NULL,
    interval VARCHAR(10) NOT NULL,           -- '1m', '5m'
    last_sync_at TIMESTAMPTZ,                -- 最終同期日時
    data_start_date DATE,                    -- データ開始日
    data_end_date DATE,                      -- データ終了日
    record_count INT DEFAULT 0,              -- レコード数
    sync_status VARCHAR(20) DEFAULT 'pending', -- pending, syncing, completed, failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_id, interval)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_sync_status_last_sync ON public.market_intraday_sync_status (last_sync_at);
CREATE INDEX IF NOT EXISTS idx_sync_status_status ON public.market_intraday_sync_status (sync_status);

-- 更新時にupdated_atを自動更新するトリガー
CREATE OR REPLACE FUNCTION update_sync_status_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_sync_status_updated ON public.market_intraday_sync_status;
CREATE TRIGGER trigger_sync_status_updated
    BEFORE UPDATE ON public.market_intraday_sync_status
    FOR EACH ROW
    EXECUTE FUNCTION update_sync_status_timestamp();

-- 完了メッセージ
DO $$
BEGIN
    RAISE NOTICE 'Intraday sync status table created successfully!';
END $$;
