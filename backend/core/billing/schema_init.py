"""
収益化 (招待コード / entitlements / Pro PDFアーカイブ) テーブル初期化

収益化計画 (EconAlpha_収益化計画_現在設計反映版_20260612) の
「10. 権限・データ管理」「14. 実装優先順位 #4」に基づく最小スキーマ。
アプリ起動時に呼び出される。auth の schema_init と同様、
CREATE TABLE IF NOT EXISTS を直接実行する (Alembic は未使用)。

設計メモ:
- role は表示権限 (既存の可視性制御で使用)、plan_code は契約商品、
  entitlement_source は権限付与理由として分離する (計画書 Table 12)。
- EconAlpha単体と Pro はどちらも role='special' のため、
  PDFアーカイブの閲覧判定は role ではなく entitlements.plan_code で行う。
- PDF本体は DB に保存しない (メタデータのみ。実体は Object Storage)。
"""
from __future__ import annotations

import logging

from sqlalchemy import text

try:
    from backend.core.database import engine
except ImportError:
    from core.database import engine

logger = logging.getLogger(__name__)


INVITE_CODES_DDL = """
CREATE TABLE IF NOT EXISTS public.invite_codes (
    id                  SERIAL PRIMARY KEY,
    code                VARCHAR(64)  UNIQUE NOT NULL,
    role_to_grant       VARCHAR(16)  NOT NULL DEFAULT 'general',
    plan_code           VARCHAR(40)  NOT NULL DEFAULT 'free',
    entitlement_source  VARCHAR(40)  NOT NULL DEFAULT 'invite',
    valid_days          INTEGER,
    max_uses            INTEGER      NOT NULL DEFAULT 1,
    used_count          INTEGER      NOT NULL DEFAULT 0,
    expires_at          TIMESTAMPTZ,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    memo                TEXT,
    created_by          INTEGER REFERENCES public.users(id),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT invite_codes_role_check
        CHECK (role_to_grant IN ('special', 'general'))
);
"""

INVITE_CODE_USES_DDL = """
CREATE TABLE IF NOT EXISTS public.invite_code_uses (
    id          SERIAL PRIMARY KEY,
    code_id     INTEGER NOT NULL REFERENCES public.invite_codes(id),
    user_id     INTEGER NOT NULL REFERENCES public.users(id),
    used_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

ENTITLEMENTS_DDL = """
CREATE TABLE IF NOT EXISTS public.entitlements (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES public.users(id),
    plan_code             VARCHAR(40) NOT NULL,
    entitlement_source    VARCHAR(40) NOT NULL,
    status                VARCHAR(20) NOT NULL DEFAULT 'active',
    current_period_start  TIMESTAMPTZ,
    current_period_end    TIMESTAMPTZ,
    discount_until        TIMESTAMPTZ,
    memo                  TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT entitlements_status_check
        CHECK (status IN ('active', 'expired', 'revoked', 'superseded'))
);
"""

ENTITLEMENTS_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_entitlements_user_status
    ON public.entitlements (user_id, status);
"""

ENTITLEMENTS_EXPIRY_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_entitlements_active_period_end
    ON public.entitlements (current_period_end)
    WHERE status = 'active';
"""

PRO_PDF_ARCHIVES_DDL = """
CREATE TABLE IF NOT EXISTS public.pro_pdf_archives (
    id                SERIAL PRIMARY KEY,
    title             TEXT        NOT NULL,
    category          VARCHAR(40) NOT NULL DEFAULT 'weekly',
    published_at      DATE,
    note_url          TEXT,
    storage_provider  VARCHAR(40) NOT NULL DEFAULT 'lightsail',
    bucket_name       VARCHAR(128),
    object_key        TEXT,
    file_size_bytes   BIGINT,
    visibility        VARCHAR(20) NOT NULL DEFAULT 'pro',
    is_active         BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def init_billing_schema() -> None:
    """収益化関連テーブルを作成 (冪等)。"""
    try:
        with engine.begin() as conn:
            conn.execute(text(INVITE_CODES_DDL))
            conn.execute(text(INVITE_CODE_USES_DDL))
            conn.execute(text(ENTITLEMENTS_DDL))
            conn.execute(text(ENTITLEMENTS_INDEX_DDL))
            conn.execute(text(ENTITLEMENTS_EXPIRY_INDEX_DDL))
            conn.execute(text(PRO_PDF_ARCHIVES_DDL))
        logger.info("[billing] invite_codes / entitlements / pro_pdf_archives tables are ready")
    except Exception as e:
        logger.error(f"[billing] failed to ensure billing tables: {e}")
