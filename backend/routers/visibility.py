"""
visibility 関連 API ルータ

エンドポイント:
    GET    /api/admin/visibility               - 全 visibility 一覧 (master)
    PUT    /api/admin/visibility/{code}        - upsert (master)
    DELETE /api/admin/visibility/{code}        - 削除 (master, public 扱いに戻る)
    GET    /api/headlines/public               - public 公開 (master が curate したもの) (認証必須)
    GET    /api/compare/candidates             - データ比較で選択可能な指標一覧 (認証必須)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

try:
    from backend.core.auth.dependencies import get_current_user, require_role
    from backend.core.auth.models import ROLE_MASTER, User
    from backend.core.database import get_db_connection
    from backend.services.visibility.visibility_service import (
        delete_visibility,
        list_all_visibilities,
        upsert_visibility,
    )
except ImportError:
    from core.auth.dependencies import get_current_user, require_role
    from core.auth.models import ROLE_MASTER, User
    from core.database import get_db_connection
    from services.visibility.visibility_service import (
        delete_visibility,
        list_all_visibilities,
        upsert_visibility,
    )

_require_master = require_role(ROLE_MASTER)

router = APIRouter(tags=["Visibility"])


# ===========================================================================
# Admin Visibility CRUD (master only)
# ===========================================================================


class VisibilityUpsertRequest(BaseModel):
    visibility: str  # 'public' | 'special' | 'master'
    reason: Optional[str] = None


@router.get("/api/admin/visibility")
def api_list_visibility(_master: User = Depends(_require_master)):
    """全 visibility 一覧 (master)"""
    return {"items": list_all_visibilities()}


@router.put("/api/admin/visibility/{indicator_code}")
def api_upsert_visibility(
    indicator_code: str,
    body: VisibilityUpsertRequest,
    master: User = Depends(_require_master),
):
    """visibility を upsert (master)"""
    try:
        result = upsert_visibility(
            indicator_code=indicator_code,
            visibility=body.visibility,
            reason=body.reason,
            updated_by=master.id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/admin/visibility/{indicator_code}")
def api_delete_visibility(
    indicator_code: str,
    _master: User = Depends(_require_master),
):
    """visibility を削除 (master) → public 扱いに戻る"""
    deleted = delete_visibility(indicator_code)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True}


# ===========================================================================
# Public headlines (master 整理ヘッドラインの一般公開)
# ===========================================================================


@router.get("/api/headlines/public")
def api_get_public_headlines(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    """master が is_public_visible=TRUE で curate したヘッドラインのみ返す。

    全ロール (general/special/master) が閲覧可能。認証必須。
    """
    conditions = ["sh.is_public_visible = TRUE"]
    params: dict = {"limit": limit, "offset": offset}

    if category_id is not None:
        conditions.append("sh.category_id = %(category_id)s")
        params["category_id"] = category_id

    where = "WHERE " + " AND ".join(conditions)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT sh.id as saved_id, sh.headline_id, sh.category_id,
                    sh.snapshot_raw, sh.snapshot_ja,
                    sh.snapshot_source_type, sh.snapshot_published_at,
                    sh.saved_at, sh.is_public_visible,
                    c.name as category_name, c.color as category_color
                FROM saved_headlines sh
                JOIN categories c ON c.id = sh.category_id
                {where}
                ORDER BY sh.saved_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

            cur.execute(
                f"SELECT COUNT(*) FROM saved_headlines sh JOIN categories c ON c.id = sh.category_id {where}",
                params,
            )
            total = cur.fetchone()[0]

    for r in rows:
        for k in ("snapshot_published_at", "saved_at"):
            if r.get(k):
                r[k] = r[k].isoformat()

    return {"items": rows, "total": total, "limit": limit, "offset": offset}


# ===========================================================================
# Compare candidates (visibility filtered)
# ===========================================================================


@router.get("/api/compare/candidates")
def api_compare_candidates(user: User = Depends(get_current_user)):
    """データ比較画面の選択可能指標一覧。

    Pattern A: ロールが見られない special/master 指標は候補から除外する。
    現状は visibility テーブルから「general/special が見られない」コードを返さない
    というシンプルな実装。フロント側で除外用に使う。

    Returns:
        {
          "blocked_codes": [...],   // このロールでは見られない indicator_code
          "role": "general"|"special"|"master"
        }
    """
    try:
        from backend.services.visibility.visibility_service import (
            VIS_MASTER,
            VIS_SPECIAL,
            list_all_visibilities,
        )
        from backend.core.auth.models import ROLE_MASTER, ROLE_SPECIAL
    except ImportError:
        from services.visibility.visibility_service import (
            VIS_MASTER,
            VIS_SPECIAL,
            list_all_visibilities,
        )
        from core.auth.models import ROLE_MASTER, ROLE_SPECIAL

    role = user.role
    items = list_all_visibilities()
    blocked: list[str] = []
    for it in items:
        vis = it.get("visibility")
        code = it.get("indicator_code")
        if vis == VIS_MASTER and role != ROLE_MASTER:
            blocked.append(code)
        elif vis == VIS_SPECIAL and role not in (ROLE_SPECIAL, ROLE_MASTER):
            blocked.append(code)

    return {"role": role, "blocked_codes": blocked}
