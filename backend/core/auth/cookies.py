"""
JWT を httpOnly Cookie として併用するためのヘルパ

設計方針:
- access_token は Authorization ヘッダ (Bearer) と Cookie の両方で受け付ける
  - SPA の fetch / axios は Authorization ヘッダで送る (既存の挙動)
  - <img src> や直リンクなど Authorization ヘッダを付けられない経路は Cookie でカバー
- Cookie は httpOnly + SameSite=Lax 固定。HTTPS 環境では Secure を有効化。
- ローカル開発 (http://localhost:3000) では Secure を無効化しないと Cookie が保存されない。

セキュリティ:
- httpOnly のため JS から token を盗めない (XSS 耐性)
- SameSite=Lax のため別ドメインからの POST は Cookie が送られない (CSRF 緩和)
- 既存の WriteOperationGuardMiddleware が更新系を全部 master に絞っているため
  CSRF 影響面はさらに小さい (master セッション奪取がない限り破壊操作は不能)
"""
from __future__ import annotations

import os
from typing import Optional

from starlette.responses import Response

ACCESS_TOKEN_COOKIE_NAME = "access_token"


def _is_secure() -> bool:
    """COOKIE_SECURE 環境変数で制御。デフォルトはローカル開発を考慮し False。

    本番では COOKIE_SECURE=true を設定する。
    """
    val = os.getenv("COOKIE_SECURE", "false").lower()
    return val in ("1", "true", "yes", "on")


def set_access_token_cookie(
    response: Response,
    token: str,
    max_age_seconds: int,
) -> None:
    """access_token を httpOnly Cookie としてセットする。"""
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=_is_secure(),
        path="/",
    )


def clear_access_token_cookie(response: Response) -> None:
    """access_token Cookie を破棄する。"""
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_is_secure(),
    )


def extract_token_from_cookie(cookie_header: Optional[str]) -> Optional[str]:
    """Cookie ヘッダ文字列から access_token を抽出する純関数。

    Starlette の Request.cookies を経由しない理由:
    - ASGI ミドルウェア (WriteOperationGuardMiddleware など) で Request を再構築する前に
      生 Header から軽量に取り出したい場合があるため
    """
    if not cookie_header:
        return None
    for raw in cookie_header.split(";"):
        item = raw.strip()
        if not item:
            continue
        if "=" not in item:
            continue
        name, _, value = item.partition("=")
        if name.strip() == ACCESS_TOKEN_COOKIE_NAME:
            return value.strip() or None
    return None
