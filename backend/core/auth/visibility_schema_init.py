"""
indicator_visibility テーブル / saved_headlines.is_public_visible カラム の初期化

設計方針:
- 既存の DDL 運用 (scripts/*.sql, schema_init.py) に合わせ、Alembic は使わず
  CREATE TABLE / ALTER TABLE IF NOT EXISTS を直接実行する。
- アプリ起動時に init_visibility_schema() を呼ぶ。冪等。
- visibility_seed.py から initial データを投入する。

テーブル: indicator_visibility
    - indicator_code (PK, VARCHAR(128))   # "country:category:indicator" 等の一意キー
    - visibility (VARCHAR(16))            # 'public' | 'special' | 'master'
    - reason (TEXT)                       # 任意メモ (なぜこの可視性か)
    - updated_at (TIMESTAMPTZ)
    - updated_by (INTEGER, FK users.id)

CHECK 制約: visibility IN ('public', 'special', 'master')

備考:
- general ロールが見られるのは visibility='public' のみ
- special ロールが見られるのは visibility IN ('public','special')
- master ロールはすべて見られる
"""
from __future__ import annotations

import logging

from sqlalchemy import text

try:
    from backend.core.database import engine
except ImportError:
    from core.database import engine

logger = logging.getLogger(__name__)


INDICATOR_VISIBILITY_DDL = """
CREATE TABLE IF NOT EXISTS public.indicator_visibility (
    indicator_code  VARCHAR(128) PRIMARY KEY,
    visibility      VARCHAR(16)  NOT NULL DEFAULT 'public',
    reason          TEXT,
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by      INTEGER REFERENCES public.users(id) ON DELETE SET NULL,
    CONSTRAINT indicator_visibility_check
        CHECK (visibility IN ('public', 'special', 'master'))
);
"""

INDICATOR_VISIBILITY_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_indicator_visibility_visibility
    ON public.indicator_visibility (visibility);
"""

# saved_headlines.is_public_visible 列の追加 (存在しない場合のみ)
# saved_headlines テーブル自体は別途 (scripts/init_*.sql 等) で作成済みの前提
SAVED_HEADLINES_PUBLIC_FLAG_DDL = """
ALTER TABLE IF EXISTS public.saved_headlines
    ADD COLUMN IF NOT EXISTS is_public_visible BOOLEAN NOT NULL DEFAULT FALSE;
"""

SAVED_HEADLINES_PUBLIC_FLAG_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_saved_headlines_public_visible
    ON public.saved_headlines (is_public_visible)
    WHERE is_public_visible = TRUE;
"""


def ensure_visibility_schema() -> None:
    """visibility 関連テーブル/カラムを作成 (存在しない場合)."""
    try:
        with engine.begin() as conn:
            conn.execute(text(INDICATOR_VISIBILITY_DDL))
            conn.execute(text(INDICATOR_VISIBILITY_INDEX_DDL))
            # saved_headlines が無くてもエラーにならないように IF EXISTS
            conn.execute(text(SAVED_HEADLINES_PUBLIC_FLAG_DDL))
            conn.execute(text(SAVED_HEADLINES_PUBLIC_FLAG_INDEX_DDL))
        logger.info("[visibility] indicator_visibility schema is ready")
    except Exception as e:
        logger.error(f"[visibility] failed to ensure visibility schema: {e}")
        raise


def init_visibility_schema() -> None:
    """起動時に一度だけ呼ぶエントリーポイント."""
    ensure_visibility_schema()
    # seed は別関数で (失敗しても起動継続できるように分離)
    try:
        from backend.core.auth.visibility_seed import seed_indicator_visibility
    except ImportError:
        from core.auth.visibility_seed import seed_indicator_visibility
    try:
        seed_indicator_visibility()
    except Exception as e:
        logger.error(f"[visibility] seed failed (non-fatal): {e}")
