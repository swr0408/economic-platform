"""
FastAPI 依存関数

- get_current_user: Authorization ヘッダ必須
- get_current_user_optional: 未ログインでも None を返す
- get_current_token_claims: 現在トークンのクレームを取得 (logout での revoke 用)
- require_role(*roles): 指定ロールのみ許可する依存ファクトリ
  - 使用例: user = Depends(require_role("master"))
  - 使用例: user = Depends(require_role("master", "special"))
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

# OpenAPI (/docs) に "Authorize" ボタンと各エンドポイントの 🔒 アイコンを表示するための
# セキュリティスキーム。実際の認証ロジックは Header 経由で行うため auto_error=False。
_bearer_scheme = HTTPBearer(auto_error=False, description="Bearer JWT token")

try:
    from backend.core.auth.cookies import ACCESS_TOKEN_COOKIE_NAME
    from backend.core.auth.models import User, VALID_ROLES
    from backend.core.auth.revocation import get_force_logout_after, is_jti_revoked
    from backend.core.auth.security import decode_access_token
    from backend.core.database import get_db
except ImportError:
    from core.auth.cookies import ACCESS_TOKEN_COOKIE_NAME
    from core.auth.models import User, VALID_ROLES
    from core.auth.revocation import get_force_logout_after, is_jti_revoked
    from core.auth.security import decode_access_token
    from core.database import get_db


# ---- 内部ユーティリティ ----


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer":
        return None
    return token


def _load_user_from_token(token: str, db: Session) -> User:
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --- Revocation チェック ---
    # 1. jti 単位のブラックリスト (logout 等で即時失効)
    jti = payload.get("jti")
    if is_jti_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 2. ユーザー単位の強制失効 (パスワード変更/無効化で iat 以前の全トークン失効)
    force_after = get_force_logout_after(user_id)
    if force_after is not None:
        iat = payload.get("iat", 0)
        if isinstance(iat, (int, float)) and iat < force_after:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return user


# ---- 公開依存関数 ----


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
    _bearer=Depends(_bearer_scheme),  # OpenAPI に security 要件を露出させるためのダミー
    db: Session = Depends(get_db),
) -> User:
    """ログイン必須エンドポイント用。ロールは問わない。

    Authorization ヘッダを優先し、無ければ httpOnly Cookie の access_token を使う。
    """
    token = _extract_token(authorization) or access_token
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _load_user_from_token(token, db)


def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
    _bearer=Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """ログインしていれば User、未ログインなら None を返す。

    Authorization ヘッダ → Cookie の順でトークンを探す。
    """
    token = _extract_token(authorization) or access_token
    if token is None:
        return None
    try:
        return _load_user_from_token(token, db)
    except HTTPException:
        return None


def get_current_token_claims(
    authorization: Optional[str] = Header(default=None),
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
    _bearer=Depends(_bearer_scheme),
) -> Dict[str, Any]:
    """現在のトークンのクレーム (jti / exp / sub 等) を取得する。

    - logout エンドポイントで revoke_jti に渡すために使用
    - get_current_user とは独立して呼べるので、logout のように
      「トークンの識別情報だけ欲しい」ケースで便利
    - 署名・期限は検証するが、revocation チェックは行わない
    - Authorization ヘッダ → Cookie の順でトークンを探す
    """
    token = _extract_token(authorization) or access_token
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(*allowed_roles: str) -> Callable[..., User]:
    """指定ロールのみアクセス可能にする依存ファクトリ。

    使用例:
        @router.get("/admin-only")
        def admin_only(user=Depends(require_role("master"))):
            ...

    将来「master のみ編集/更新」エンドポイントを増やす際は、ルーター関数の
    引数に `user = Depends(require_role("master"))` を追加するだけで済む。
    """
    # 引数バリデーション (タイポ検知)
    for r in allowed_roles:
        if r not in VALID_ROLES:
            raise ValueError(
                f"Unknown role '{r}'. Must be one of {VALID_ROLES}"
            )

    allowed = set(allowed_roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role in {sorted(allowed)}",
            )
        return user

    return _dep
