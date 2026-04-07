"""
認証・認可モジュール

- models: SQLAlchemy User モデル
- schemas: Pydantic リクエスト/レスポンス
- security: パスワードハッシュ化 (scrypt) + JWT
- dependencies: FastAPI 依存関数 (get_current_user, require_role)
- schema_init: users テーブル DDL + 初期 master 作成
"""
from .dependencies import (
    get_current_token_claims,
    get_current_user,
    get_current_user_optional,
    require_role,
)
from .models import ROLE_GENERAL, ROLE_MASTER, ROLE_SPECIAL, User, VALID_ROLES
from .revocation import (
    is_jti_revoked,
    revoke_all_for_user,
    revoke_jti,
)
from .schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

__all__ = [
    "User",
    "VALID_ROLES",
    "ROLE_MASTER",
    "ROLE_SPECIAL",
    "ROLE_GENERAL",
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    "get_current_user",
    "get_current_user_optional",
    "get_current_token_claims",
    "require_role",
    "revoke_jti",
    "revoke_all_for_user",
    "is_jti_revoked",
]
