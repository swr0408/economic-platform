"""
users テーブル初期化 + 初期 master ユーザー seed

アプリ起動時に呼び出される。既存の DDL 運用 (scripts/*.sql) に合わせ、
CREATE TABLE IF NOT EXISTS を直接実行する (Alembic は未使用)。

環境変数:
- INITIAL_MASTER_USERNAME: 初期 master のユーザー名 (任意)
- INITIAL_MASTER_PASSWORD: 初期 master のパスワード (任意)

両方がセットされており、かつ users テーブルに master が1人も存在しない場合にのみ
新規作成する。既存 master がいれば何もしない (冪等)。
"""
from __future__ import annotations

import logging
import os

from sqlalchemy import text

try:
    from backend.core.auth.models import ROLE_MASTER, User
    from backend.core.auth.security import hash_password
    from backend.core.database import SessionLocal, engine
except ImportError:
    from core.auth.models import ROLE_MASTER, User
    from core.auth.security import hash_password
    from core.database import SessionLocal, engine

logger = logging.getLogger(__name__)


USERS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS public.users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(64)  UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE,
    password_hash   TEXT         NOT NULL,
    role            VARCHAR(16)  NOT NULL DEFAULT 'general',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at   TIMESTAMPTZ,
    CONSTRAINT users_role_check CHECK (role IN ('master', 'special', 'general'))
);
"""

USERS_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_users_username ON public.users (username);
"""


def ensure_users_table() -> None:
    """users テーブルを作成 (存在しない場合)。"""
    try:
        with engine.begin() as conn:
            conn.execute(text(USERS_TABLE_DDL))
            conn.execute(text(USERS_INDEX_DDL))
        logger.info("[auth] users table is ready")
    except Exception as e:
        logger.error(f"[auth] failed to ensure users table: {e}")
        raise


def seed_initial_master() -> None:
    """環境変数から初期 master を作成 (master 不在時のみ)。"""
    username = os.getenv("INITIAL_MASTER_USERNAME")
    password = os.getenv("INITIAL_MASTER_PASSWORD")
    if not username or not password:
        logger.info(
            "[auth] INITIAL_MASTER_USERNAME/PASSWORD not set; skipping master seed"
        )
        return

    db = SessionLocal()
    try:
        existing_master = (
            db.query(User).filter(User.role == ROLE_MASTER).first()
        )
        if existing_master is not None:
            logger.info(
                f"[auth] master user already exists (id={existing_master.id}); skip seed"
            )
            return

        # 同名ユーザーが general などで既に存在する場合はスキップ (人手で調整)
        existing_same_name = (
            db.query(User).filter(User.username == username).first()
        )
        if existing_same_name is not None:
            logger.warning(
                f"[auth] user '{username}' already exists with role "
                f"'{existing_same_name.role}'. Not changing role automatically."
            )
            return

        user = User(
            username=username,
            password_hash=hash_password(password),
            role=ROLE_MASTER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        logger.info(
            f"[auth] seeded initial master user '{username}' (id={user.id})"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[auth] failed to seed initial master: {e}")
    finally:
        db.close()


def init_auth_schema() -> None:
    """起動時に一度だけ呼ぶエントリーポイント。"""
    ensure_users_table()
    seed_initial_master()
