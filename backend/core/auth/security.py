"""
パスワードハッシュ化 & JWT ユーティリティ

設計方針:
- パスワードハッシュは標準ライブラリ `hashlib.scrypt` のみを使用し、新規依存追加を回避
  - OWASP 推奨の scrypt (RFC 7914)
  - フォーマット: "scrypt$n$r$p$salt_b64$hash_b64"
- JWT は PyJWT を使用 (HS256)
- 秘密鍵は環境変数 AUTH_JWT_SECRET から取得。未設定時は起動時警告つきデフォルト
  (ローカル開発向け。本番では必ず環境変数で上書きすること)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

logger = logging.getLogger(__name__)

# --- パスワードハッシュ ---

# scrypt パラメータ (OWASP 2023 推奨の下限近辺)
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_SALT_BYTES = 16


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(data: str) -> bytes:
    pad = 4 - (len(data) % 4)
    return base64.urlsafe_b64decode(data + ("=" * pad))


def hash_password(plain: str) -> str:
    """平文パスワードをハッシュ化する。

    フォーマット: scrypt$n$r$p$salt$hash
    """
    if not isinstance(plain, str) or len(plain) == 0:
        raise ValueError("password must be a non-empty string")
    salt = secrets.token_bytes(_SCRYPT_SALT_BYTES)
    dk = hashlib.scrypt(
        plain.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=64 * 1024 * 1024,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(dk)}"


def verify_password(plain: str, stored: str) -> bool:
    """平文パスワードと保存済みハッシュを照合する。"""
    if not stored:
        return False
    try:
        scheme, n_str, r_str, p_str, salt_b64, hash_b64 = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    try:
        n = int(n_str)
        r = int(r_str)
        p = int(p_str)
        salt = _b64d(salt_b64)
        expected = _b64d(hash_b64)
    except Exception:
        return False
    try:
        dk = hashlib.scrypt(
            plain.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=64 * 1024 * 1024,
        )
    except Exception:
        return False
    return hmac.compare_digest(dk, expected)


# --- JWT ---

_DEFAULT_DEV_SECRET = "dev-only-secret-change-me-in-production"

JWT_ALGORITHM = "HS256"


def _get_secret() -> str:
    secret = os.getenv("AUTH_JWT_SECRET")
    if secret:
        return secret
    logger.warning(
        "AUTH_JWT_SECRET is not set. Using an insecure default secret. "
        "Set AUTH_JWT_SECRET in your environment for anything beyond local dev."
    )
    return _DEFAULT_DEV_SECRET


def get_token_expire_seconds() -> int:
    try:
        hours = int(os.getenv("AUTH_JWT_EXPIRE_HOURS", "12"))
    except ValueError:
        hours = 12
    return hours * 3600


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    expires_in: Optional[int] = None,
) -> str:
    """JWT を発行する。

    `jti` (JWT ID) を必ず付与する。revocation (logout による即時失効) に使用する。
    """
    now = datetime.now(tz=timezone.utc)
    ttl = expires_in if expires_in is not None else get_token_expire_seconds()
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """JWT をデコードする。期限切れや改ざんは例外送出。"""
    return jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
