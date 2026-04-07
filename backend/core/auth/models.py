"""
User SQLAlchemy モデル

users テーブル定義。既存の Base (backend/core/database.py) を再利用。
"""
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func,
)

try:
    from backend.core.database import Base
except ImportError:
    from core.database import Base


# ロール定数 - コード全体で一貫して使用する
ROLE_MASTER = "master"
ROLE_SPECIAL = "special"
ROLE_GENERAL = "general"
VALID_ROLES = (ROLE_MASTER, ROLE_SPECIAL, ROLE_GENERAL)


class User(Base):
    """アプリケーションユーザー"""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('master', 'special', 'general')",
            name="users_role_check",
        ),
        {"schema": "public"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(16), nullable=False, default=ROLE_GENERAL)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} username={self.username} role={self.role}>"
