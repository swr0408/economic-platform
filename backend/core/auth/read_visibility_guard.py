"""
read 系リクエストの可視性制御ミドルウェア

設計方針:
- WriteOperationGuardMiddleware と並走し、read (GET) リクエストのうち
  visibility 制御対象のものをロールでブロックする
- EconAlpha は会員制サイトのため、/api/* および /static/screenshots/ 配下の
  GET は原則すべて認証必須
  (= public visibility = 「ログイン済み一般ユーザ向け公開」を意味する)
- 認証例外プレフィックス (_NEVER_REQUIRE_AUTH_PREFIXES) のみ未ログインで素通し
  (ログイン/登録/health/docs/シーズナリティ画像 等)
- /static/screenshots/ は special/master 限定の指標画像が含まれるため、
  未ログインには 401 を返す (画像 URL が漏洩しても匿名アクセス不可)
- 制御対象パス (= path_resolver.resolve_indicator_code() が non-None) は
  さらに visibility に応じて role 判定を行う
- 制御対象外パスでも認証は要求される (= 未ログインは 401)
- POST/PUT/PATCH/DELETE は WriteOperationGuardMiddleware に任せる (read のみ判定)

判定の純関数 should_block_read は分離してテスト容易にする。
"""
from __future__ import annotations

import asyncio

from typing import Any, Dict, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

try:
    from backend.core.auth.cookies import extract_token_from_cookie
    from backend.core.auth.guard_executor import AUTH_GUARD_EXECUTOR
    from backend.core.auth.revocation import get_force_logout_after, is_jti_revoked
    from backend.core.auth.security import decode_access_token
    from backend.services.visibility.path_resolver import resolve_indicator_code
    from backend.services.visibility.visibility_service import (
        VIS_PUBLIC,
        get_visibility,
        _can_view_visibility,
    )
except ImportError:
    from core.auth.cookies import extract_token_from_cookie
    from core.auth.guard_executor import AUTH_GUARD_EXECUTOR
    from core.auth.revocation import get_force_logout_after, is_jti_revoked
    from core.auth.security import decode_access_token
    from services.visibility.path_resolver import resolve_indicator_code
    from services.visibility.visibility_service import (
        VIS_PUBLIC,
        get_visibility,
        _can_view_visibility,
    )


# 認証チェック自体をスキップする (未ログインでも通す) パス
# このリスト以外の /api/* および /static/screenshots/ GET はすべて認証必須
# (= EconAlpha 会員制)
# NOTE: /static/screenshots/ は visibility 制御対象 (special/master 限定指標の
# 画像を含む) のため、このリストには入れない。/static/seasonality/ のみ公開。
_NEVER_REQUIRE_AUTH_PREFIXES = (
    "/api/auth/",               # ログイン/登録/me/logout 等
    "/api/health",              # ヘルスチェック (監視用)
    "/health",                  # ヘルスチェック (監視用)
    "/docs",                    # OpenAPI UI
    "/redoc",
    "/openapi.json",
    "/static/seasonality/",     # シーズナリティ画像 (公開可)
)


# ReadVisibilityGuardMiddleware の処理対象となるパス接頭辞
# ここに該当しないパス (SPA の / 等) は素通しする
_GUARDED_PREFIXES = (
    "/api/",
    "/static/screenshots/",
)


def should_block_read(
    method: str,
    path: str,
    role: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """read リクエストをブロックすべきか判定。

    Returns:
        (block, indicator_code) のタプル。
        - block=True なら 403 を返すべき
        - indicator_code は監査ログ用
    """
    if method != "GET":
        return False, None

    code = resolve_indicator_code(path)
    if code is None:
        return False, None

    vis = get_visibility(code)
    if vis == VIS_PUBLIC:
        return False, code

    if not _can_view_visibility(role, vis):
        return True, code

    return False, code


def _unauth(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_role(
    request: Request,
) -> Tuple[Optional[str], Optional[JSONResponse], Optional[Dict[str, Any]]]:
    """Authorization ヘッダから role を取り出す。失敗時はエラーレスポンスを返す。"""
    authz = request.headers.get("authorization") or request.headers.get("Authorization")
    token: Optional[str] = None
    if authz:
        parts = authz.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None, _unauth("Invalid authorization header"), None
        token = parts[1]
    else:
        # Authorization が無い場合は httpOnly Cookie を試す (SPA 経路以外用)
        cookie_header = request.headers.get("cookie") or request.headers.get("Cookie")
        token = extract_token_from_cookie(cookie_header)

    if not token:
        return None, _unauth("Not authenticated"), None

    try:
        payload = decode_access_token(token)
    except Exception:
        return None, _unauth("Invalid or expired token"), None

    jti = payload.get("jti")
    if is_jti_revoked(jti):
        return None, _unauth("Token revoked"), payload

    sub = payload.get("sub")
    try:
        user_id = int(sub) if sub is not None else None
    except (TypeError, ValueError):
        return None, _unauth("Invalid token subject"), payload
    if user_id is not None:
        force_after = get_force_logout_after(user_id)
        if force_after is not None:
            iat = payload.get("iat", 0)
            if isinstance(iat, (int, float)) and iat < force_after:
                return None, _unauth("Token revoked"), payload

    role = payload.get("role")
    return role, None, payload


class ReadVisibilityGuardMiddleware(BaseHTTPMiddleware):
    """read 系の可視性ガードミドルウェア。

    - GET 以外は素通し (write_guard が処理)
    - _GUARDED_PREFIXES (/api/, /static/screenshots/) 以外は素通し
      (SPA の / や /static/seasonality/ 等)
    - _NEVER_REQUIRE_AUTH_PREFIXES に該当するパスは素通し
      (ログイン/health/docs/seasonality 画像 等。未ログインでも通す)
    - それ以外の /api/* および /static/screenshots/* は認証必須
      (= EconAlpha は会員制)
    - 制御対象パス (path_resolver が non-None) は更に visibility に応じて
      role 判定し、403 を返す
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method.upper()

        # GET 以外は対象外 (write_guard に任せる)
        if method != "GET":
            return await call_next(request)

        # ガード対象外のパスは素通し (SPA, /static/seasonality/ 等)
        if not any(path.startswith(p) for p in _GUARDED_PREFIXES):
            return await call_next(request)

        # 認証不要なパス (ログイン/health/docs 等)
        if any(path.startswith(p) for p in _NEVER_REQUIRE_AUTH_PREFIXES):
            return await call_next(request)

        # 認証チェック (会員制サイトのため /api/* GET は全て認証必須)
        # _extract_role は同期 Redis 呼び出しを含むため、イベントループ上で
        # 直接実行せず専用スレッドプールに退避する (Redis 遅延時の全停止防止)
        role, err, _payload = await asyncio.get_running_loop().run_in_executor(
            AUTH_GUARD_EXECUTOR, _extract_role, request
        )
        if err is not None:
            return err

        # 制御対象パスかどうか
        code = resolve_indicator_code(path)
        if code is None:
            # 制御対象外 = public (ログイン済みなら誰でも可) → 通す
            return await call_next(request)

        # visibility 判定
        block, _ = should_block_read(method, path, role)
        if block:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"Access denied for indicator '{code}' (your role: {role})",
                    "indicator_code": code,
                },
            )

        return await call_next(request)
