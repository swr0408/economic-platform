"""
認証関連の Pydantic スキーマ
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Role = Literal["master", "special", "general"]


class RegisterRequest(BaseModel):
    """新規登録リクエスト

    注意: role は受け付けない。常に 'general' で作成される。
    昇格は DB 直接 or master 専用 API 経由で行う。
    """

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("username")
    @classmethod
    def _username_charset(cls, v: str) -> str:
        # 英数・アンダースコア・ハイフンのみ
        if not all(ch.isalnum() or ch in ("_", "-") for ch in v):
            raise ValueError(
                "username must contain only alphanumeric characters, '_' or '-'"
            )
        return v

    @field_validator("email")
    @classmethod
    def _email_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        # pydantic[email] を追加依存にしないため軽量チェック
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("email format is invalid")
        return v


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # 秒
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    """自分自身のパスワード変更リクエスト"""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class UpdateUserRoleRequest(BaseModel):
    """master による他ユーザーのロール変更リクエスト"""

    role: Role


class UpdateUserActiveRequest(BaseModel):
    """master による他ユーザーの有効/無効切替リクエスト"""

    is_active: bool
