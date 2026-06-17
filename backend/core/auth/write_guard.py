"""
更新系 endpoint の master ロール強制ミドルウェア

設計方針:
- ホワイトリスト方式 (許可しないものは更新系扱い → master 必須)
- 認証系 (/api/auth/*) はミドルウェアでは判定せず通過させ、router 内の require_role に任せる
- GET でも ?force_refresh=true / ?refresh=true は更新トリガ扱い
- Headlines / Categories CRUD は master 化済 (router 側 require_role + ミドルウェアで二重保証)
- Redis ベースの jti / force_logout_after 失効チェックも実施

判定の純関数 `is_write_request` はテスト容易性のためミドルウェアと分離している。

非対象 (素通し):
- /api/auth/* (認証系。auth router 内で個別に require_role しているため)
- GET 全般 (force_refresh / refresh クエリが無いもの) は ReadVisibilityGuardMiddleware で判定

対象 (master 必須):
- POST/PUT/PATCH/DELETE のすべて (Headlines/Categories の CRUD 含む)
- GET でも ?force_refresh=true / ?refresh=true が付くもの
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import asyncio

try:
    from backend.core.auth.audit_log import audit_write_operation
    from backend.core.auth.cookies import extract_token_from_cookie
    from backend.core.auth.guard_executor import AUTH_GUARD_EXECUTOR
    from backend.core.auth.models import ROLE_MASTER
    from backend.core.auth.revocation import get_force_logout_after, is_jti_revoked
    from backend.core.auth.security import decode_access_token
except ImportError:
    from core.auth.audit_log import audit_write_operation
    from core.auth.cookies import extract_token_from_cookie
    from core.auth.guard_executor import AUTH_GUARD_EXECUTOR
    from core.auth.models import ROLE_MASTER
    from core.auth.revocation import get_force_logout_after, is_jti_revoked
    from core.auth.security import decode_access_token


# ミドルウェアでは判定せず通過させるパス接頭辞
# (router 内で個別に require_role しているもの、認証フロー自体)
_ALWAYS_PASSTHROUGH_PREFIXES = (
    "/api/auth/",
)

# Headlines / Categories CRUD は master 化したため、whitelist は空。
# (router 側で require_role(ROLE_MASTER) も付与しており、二重チェックでフェイルセーフ)
_HEADLINES_NON_WRITE_SUFFIXES: tuple[str, ...] = ()
_NON_WRITE_PREFIXES: tuple[str, ...] = ()


def _truthy(v: Optional[str]) -> bool:
    if v is None:
        return False
    return v.lower() in ("true", "1", "yes", "on")


def is_write_request(method: str, path: str, query_params) -> bool:
    """更新系リクエスト判定 (純関数, テスト容易).

    Args:
        method: HTTP メソッド (大文字)
        path: リクエストパス
        query_params: dict-like (starlette QueryParams など)

    Returns:
        True なら更新系 (master 権限が必要)
    """
    # 認証系・常時通過リスト
    if any(path.startswith(p) for p in _ALWAYS_PASSTHROUGH_PREFIXES):
        return False

    if method == "GET":
        # GET でも ?force_refresh=true / ?refresh=true は事実上の更新トリガ
        if _truthy(query_params.get("force_refresh")):
            return True
        if _truthy(query_params.get("refresh")):
            return True
        return False

    if method in ("POST", "PUT", "PATCH", "DELETE"):
        # 旧バージョンとの互換のための whitelist (現状は空)
        if _NON_WRITE_PREFIXES and any(path.startswith(p) for p in _NON_WRITE_PREFIXES):
            return False
        if _HEADLINES_NON_WRITE_SUFFIXES and path.startswith("/api/headlines/"):
            if any(path.endswith(s) for s in _HEADLINES_NON_WRITE_SUFFIXES):
                return False
        return True

    # OPTIONS / HEAD 等は CORS preflight 含めて通過
    return False


def _unauth(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_role(
    request: Request,
) -> Tuple[Optional[str], Optional[JSONResponse], Optional[Dict[str, Any]]]:
    """Authorization ヘッダから role を取り出す。失敗時はエラーレスポンスを返す。

    revoke 状態 (jti ブラックリスト / force_logout_after) もチェックする。

    Returns:
        (role, error_response, payload) のタプル。
        - 成功時: (role, None, payload)
        - 失敗時: (None, JSONResponse, None or partial payload)
        payload は監査ログ用 (user_id / username の取り出し)。
    """
    authz = request.headers.get("authorization") or request.headers.get("Authorization")
    token: Optional[str] = None
    if authz:
        parts = authz.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None, _unauth("Invalid authorization header"), None
        token = parts[1]
    else:
        # Authorization が無い場合は httpOnly Cookie を試す
        cookie_header = request.headers.get("cookie") or request.headers.get("Cookie")
        token = extract_token_from_cookie(cookie_header)

    if not token:
        return None, _unauth("Not authenticated"), None

    try:
        payload = decode_access_token(token)
    except Exception:  # noqa: BLE001 - jwt の各種例外を一括 401 化
        return None, _unauth("Invalid or expired token"), None

    # jti ブラックリスト
    jti = payload.get("jti")
    if is_jti_revoked(jti):
        return None, _unauth("Token revoked"), payload

    # force_logout_after による強制失効
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


class WriteOperationGuardMiddleware(BaseHTTPMiddleware):
    """更新系リクエストを master ロールに制限するミドルウェア.

    - 判定は `is_write_request` に委譲 (純関数)
    - 通過対象でない場合は call_next せずに即時 401/403 を返す
    - 通過する場合は何もせず後段に委譲する (router 内の依存関数で再度 require_role が
      かかる場合もあるが、二重チェックで害は無い)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method.upper()

        if not is_write_request(method, path, request.query_params):
            return await call_next(request)

        # _extract_role は同期 Redis 呼び出しを含むため、イベントループ上で
        # 直接実行せず専用スレッドプールに退避する (Redis 遅延時の全停止防止)
        role, err, payload = await asyncio.get_running_loop().run_in_executor(
            AUTH_GUARD_EXECUTOR, _extract_role, request
        )
        client_ip = request.client.host if request.client else None

        if err is not None:
            audit_write_operation(
                method=method,
                path=path,
                user_id=_safe_user_id(payload),
                username=(payload or {}).get("username") if payload else None,
                role=(payload or {}).get("role") if payload else None,
                status_code=err.status_code,
                client_ip=client_ip,
            )
            return err
        if role != ROLE_MASTER:
            audit_write_operation(
                method=method,
                path=path,
                user_id=_safe_user_id(payload),
                username=(payload or {}).get("username") if payload else None,
                role=role,
                status_code=403,
                client_ip=client_ip,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Requires role in ['master']"},
            )

        response = await call_next(request)
        audit_write_operation(
            method=method,
            path=path,
            user_id=_safe_user_id(payload),
            username=(payload or {}).get("username") if payload else None,
            role=role,
            status_code=response.status_code,
            client_ip=client_ip,
        )
        return response


def _safe_user_id(payload: Optional[Dict[str, Any]]) -> Optional[int]:
    if not payload:
        return None
    sub = payload.get("sub")
    try:
        return int(sub) if sub is not None else None
    except (TypeError, ValueError):
        return None
