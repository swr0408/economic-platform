"""
認証 API エンドポイント

- POST   /api/auth/register           新規登録 (常に role='general')
- POST   /api/auth/login               ログイン (username + password)
- GET    /api/auth/me                  現在ユーザー取得
- POST   /api/auth/logout              ログアウト (現在トークンを Redis jti ブラックリスト登録)
- POST   /api/auth/change-password     自分自身のパスワード変更 (全発行済みトークン強制失効)
- GET    /api/auth/users               ユーザー一覧 (master のみ)
- PATCH  /api/auth/users/{id}/role     ロール変更 (master のみ)
- PATCH  /api/auth/users/{id}/active   有効/無効切替 (master のみ)

設計メモ:
- JWT の即時失効は Redis の jti ブラックリスト (core.auth.revocation) で行う
- Redis 障害時は fail-open: revoke 判定がスキップされるが、JWT 署名検証と exp は有効
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

try:
    from backend.core.auth.cookies import (
        clear_access_token_cookie,
        set_access_token_cookie,
    )
    from backend.core.auth.dependencies import (
        get_current_token_claims,
        get_current_user,
        require_role,
    )
    from backend.core.auth.models import ROLE_GENERAL, ROLE_MASTER, User
    from backend.core.auth.revocation import revoke_all_for_user, revoke_jti
    from backend.core.auth.schemas import (
        ChangePasswordRequest,
        LoginRequest,
        RegisterRequest,
        TokenResponse,
        UpdateUserActiveRequest,
        UpdateUserRoleRequest,
        UserResponse,
    )
    from backend.core.auth.security import (
        create_access_token,
        get_token_expire_seconds,
        hash_password,
        verify_password,
    )
    from backend.core.database import get_db
except ImportError:
    from core.auth.cookies import (
        clear_access_token_cookie,
        set_access_token_cookie,
    )
    from core.auth.dependencies import (
        get_current_token_claims,
        get_current_user,
        require_role,
    )
    from core.auth.models import ROLE_GENERAL, ROLE_MASTER, User
    from core.auth.revocation import revoke_all_for_user, revoke_jti
    from core.auth.schemas import (
        ChangePasswordRequest,
        LoginRequest,
        RegisterRequest,
        TokenResponse,
        UpdateUserActiveRequest,
        UpdateUserRoleRequest,
        UserResponse,
    )
    from core.auth.security import (
        create_access_token,
        get_token_expire_seconds,
        hash_password,
        verify_password,
    )
    from core.database import get_db


router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _issue_token(user: User, response: Optional[Response] = None) -> TokenResponse:
    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )
    expires_in = get_token_expire_seconds()
    # 併用: httpOnly Cookie にも同じ token を載せる。
    # <img src> 等 Authorization ヘッダを送れない経路のため。
    if response is not None:
        set_access_token_cookie(response, token, expires_in)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


# ---------- 認証フロー ----------


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """新規登録。常に role='general' で作成する。"""
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken",
        )
    if payload.email:
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=ROLE_GENERAL,  # 自己申告による昇格を防ぐ
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _issue_token(user, response)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """ログイン。ユーザー名+パスワードで JWT を発行する。"""
    user = db.query(User).filter(User.username == payload.username).first()

    # ユーザー不在とパスワード不一致はどちらも同じメッセージにする
    # (ユーザー存在の有無を漏らさない)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    user.last_login_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(user)

    return _issue_token(user, response)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    """現在ログイン中のユーザー情報を取得する。"""
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    claims: Dict[str, Any] = Depends(get_current_token_claims),
):
    """ログアウト。現在のトークンの jti を Redis ブラックリストに登録して即時失効させる。

    Redis が落ちている場合は書き込み失敗となり、フロントエンド側のトークン破棄のみが
    効く (従来の挙動と同じ)。このレベルでは 204 を返す。

    httpOnly Cookie 併用版では access_token Cookie も破棄する。
    """
    jti = claims.get("jti")
    exp = claims.get("exp")
    if jti:
        revoke_jti(jti, exp if isinstance(exp, int) else None)
    clear_access_token_cookie(response)
    return None


# ---------- 自分自身のパスワード変更 ----------


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """自分自身のパスワードを変更する。

    - 現パスワード照合を必須にする (セッション奪取耐性)
    - 変更成功時は、発行済み全トークンを強制失効させる
      (次回以降の全リクエストで 401 になる → 再ログインを要求)
    """
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from current password",
        )

    user.password_hash = hash_password(payload.new_password)
    db.commit()

    # パスワード変更以前に発行された全トークンを強制失効
    revoke_all_for_user(user.id)
    # 同時に Cookie 経由のセッションも破棄
    clear_access_token_cookie(response)
    return None


# ---------- master 専用: ユーザー管理 ----------


@router.get(
    "/users",
    response_model=List[UserResponse],
)
def list_users(
    _master: User = Depends(require_role(ROLE_MASTER)),
    db: Session = Depends(get_db),
):
    """ユーザー一覧を返す (master 限定)。"""
    users = db.query(User).order_by(User.id.asc()).all()
    return [UserResponse.model_validate(u) for u in users]


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    master: User = Depends(require_role(ROLE_MASTER)),
    db: Session = Depends(get_db),
):
    """指定ユーザーのロールを変更する (master 限定)。

    - 自分自身のロールは変更不可 (master が誤って自分を降格するのを防ぐ)
    - ロール変更は即時反映させるため、対象ユーザーの発行済み全トークンを強制失効
    """
    if user_id == master.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    target.role = payload.role
    db.commit()
    db.refresh(target)

    # ロール変更は次のリクエストから反映されるべきなので発行済みトークンを失効
    revoke_all_for_user(target.id)
    return UserResponse.model_validate(target)


@router.patch("/users/{user_id}/active", response_model=UserResponse)
def update_user_active(
    user_id: int,
    payload: UpdateUserActiveRequest,
    master: User = Depends(require_role(ROLE_MASTER)),
    db: Session = Depends(get_db),
):
    """指定ユーザーの有効/無効を切り替える (master 限定)。

    - 自分自身の無効化は不可
    - 無効化した場合は対象ユーザーの発行済み全トークンを強制失効
    """
    if user_id == master.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself",
        )
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    target.is_active = bool(payload.is_active)
    db.commit()
    db.refresh(target)

    if not target.is_active:
        revoke_all_for_user(target.id)
    return UserResponse.model_validate(target)
