"""
収益化管理 API (master 専用) + Pro 向け PDF アーカイブ閲覧 API

master 専用 (WriteOperationGuardMiddleware + require_role の二重防御):
- POST   /api/admin/billing/invites              招待コード発行
- GET    /api/admin/billing/invites              招待コード一覧
- DELETE /api/admin/billing/invites/{id}         招待コード無効化
- GET    /api/admin/billing/entitlements         entitlement 一覧 (user_id 絞込可)
- POST   /api/admin/billing/entitlements         手動付与 (手動決済の入金反映)
- DELETE /api/admin/billing/entitlements/{uid}   即時取り消し (Free へ)
- POST   /api/admin/billing/sweep                期限切れスイープの手動実行
- POST   /api/admin/billing/pdf-archives         PDF メタデータ登録
- GET    /api/admin/billing/pdf-archives         PDF メタデータ一覧 (管理用)
- PATCH  /api/admin/billing/pdf-archives/{id}    PDF メタデータ更新/無効化

ログイン済みユーザー向け:
- GET /api/billing/me                            自分のプラン状態
- GET /api/pro/pdf-archives                      Pro: PDF 一覧 (メタデータ)
- GET /api/pro/pdf-archives/{id}/url             Pro: 短時間署名URL発行
  ※ Object Storage 未設定の間は 503 を返すスタブ (pdf_storage.py 参照)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text

try:
    from backend.core.auth.dependencies import get_current_user, require_role
    from backend.core.auth.models import ROLE_MASTER, User
    from backend.core.billing import entitlement_service, invite_service
    from backend.core.billing.pdf_storage import (
        ObjectStorageNotConfigured,
        generate_presigned_url,
    )
    from backend.core.database import SessionLocal
except ImportError:
    from core.auth.dependencies import get_current_user, require_role
    from core.auth.models import ROLE_MASTER, User
    from core.billing import entitlement_service, invite_service
    from core.billing.pdf_storage import (
        ObjectStorageNotConfigured,
        generate_presigned_url,
    )
    from core.database import SessionLocal

router = APIRouter(tags=["Billing"])


# ---------------------------------------------------------------------------
# スキーマ
# ---------------------------------------------------------------------------

class CreateInviteRequest(BaseModel):
    role_to_grant: str = Field(default="general", pattern="^(general|special)$")
    plan_code: str = Field(default="free", max_length=40)
    entitlement_source: str = Field(default="invite", max_length=40)
    valid_days: Optional[int] = Field(default=None, ge=1, le=3660)
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_at: Optional[datetime] = None
    memo: Optional[str] = Field(default=None, max_length=500)


class GrantEntitlementRequest(BaseModel):
    user_id: int
    plan_code: str = Field(..., max_length=40)
    entitlement_source: str = Field(default="manual_payment", max_length=40)
    valid_days: Optional[int] = Field(default=None, ge=1, le=3660)
    current_period_end: Optional[datetime] = None
    discount_until: Optional[datetime] = None
    memo: Optional[str] = Field(default=None, max_length=500)


class CreatePdfArchiveRequest(BaseModel):
    title: str = Field(..., max_length=300)
    category: str = Field(default="weekly", max_length=40)
    published_at: Optional[str] = None  # YYYY-MM-DD
    note_url: Optional[str] = Field(default=None, max_length=500)
    storage_provider: str = Field(default="lightsail", max_length=40)
    bucket_name: Optional[str] = Field(default=None, max_length=128)
    object_key: Optional[str] = Field(default=None, max_length=500)
    file_size_bytes: Optional[int] = None
    visibility: str = Field(default="pro", pattern="^(pro|special|master)$")


class UpdatePdfArchiveRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    category: Optional[str] = Field(default=None, max_length=40)
    published_at: Optional[str] = None
    note_url: Optional[str] = Field(default=None, max_length=500)
    bucket_name: Optional[str] = Field(default=None, max_length=128)
    object_key: Optional[str] = Field(default=None, max_length=500)
    file_size_bytes: Optional[int] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# master: 招待コード
# ---------------------------------------------------------------------------

@router.post("/api/admin/billing/invites", status_code=status.HTTP_201_CREATED)
def create_invite(
    payload: CreateInviteRequest,
    master: User = Depends(require_role(ROLE_MASTER)),
) -> Dict[str, Any]:
    """招待コードを発行する (βモニター招待・手動オンボーディング用)"""
    if payload.plan_code not in entitlement_service.VALID_PLAN_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"plan_code must be one of {entitlement_service.VALID_PLAN_CODES}",
        )
    return invite_service.create_invite_code(
        created_by=master.id,
        role_to_grant=payload.role_to_grant,
        plan_code=payload.plan_code,
        entitlement_source=payload.entitlement_source,
        valid_days=payload.valid_days,
        max_uses=payload.max_uses,
        expires_at=payload.expires_at,
        memo=payload.memo,
    )


@router.get("/api/admin/billing/invites")
def list_invites(
    include_inactive: bool = Query(False),
    _master: User = Depends(require_role(ROLE_MASTER)),
) -> List[Dict[str, Any]]:
    return invite_service.list_invite_codes(include_inactive=include_inactive)


@router.delete("/api/admin/billing/invites/{code_id}")
def deactivate_invite(
    code_id: int,
    _master: User = Depends(require_role(ROLE_MASTER)),
) -> Dict[str, Any]:
    ok = invite_service.deactivate_invite_code(code_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Invite code not found")
    return {"success": True}


# ---------------------------------------------------------------------------
# master: entitlements
# ---------------------------------------------------------------------------

@router.get("/api/admin/billing/entitlements")
def list_entitlements(
    user_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    _master: User = Depends(require_role(ROLE_MASTER)),
) -> List[Dict[str, Any]]:
    """entitlement 一覧 (手動決済の期限管理・β移行判断用)"""
    conditions = ["1=1"]
    params: Dict[str, Any] = {}
    if user_id is not None:
        conditions.append("e.user_id = :uid")
        params["uid"] = user_id
    if status_filter is not None:
        conditions.append("e.status = :status")
        params["status"] = status_filter

    with SessionLocal() as session:
        rows = session.execute(text(f"""
            SELECT e.id, e.user_id, u.username, u.role, e.plan_code,
                   e.entitlement_source, e.status,
                   e.current_period_start, e.current_period_end,
                   e.discount_until, e.memo, e.created_at
            FROM entitlements e
            JOIN users u ON u.id = e.user_id
            WHERE {' AND '.join(conditions)}
            ORDER BY e.created_at DESC
            LIMIT 500
        """), params).fetchall()

    return [{
        "id": r[0], "user_id": r[1], "username": r[2], "role": r[3],
        "plan_code": r[4], "entitlement_source": r[5], "status": r[6],
        "current_period_start": r[7].isoformat() if r[7] else None,
        "current_period_end": r[8].isoformat() if r[8] else None,
        "discount_until": r[9].isoformat() if r[9] else None,
        "memo": r[10],
        "created_at": r[11].isoformat() if r[11] else None,
    } for r in rows]


@router.post("/api/admin/billing/entitlements", status_code=status.HTTP_201_CREATED)
def grant_entitlement_api(
    payload: GrantEntitlementRequest,
    _master: User = Depends(require_role(ROLE_MASTER)),
) -> Dict[str, Any]:
    """手動で entitlement を付与する (銀行振込/PayPal入金の反映用)"""
    try:
        return entitlement_service.grant_entitlement(
            user_id=payload.user_id,
            plan_code=payload.plan_code,
            entitlement_source=payload.entitlement_source,
            valid_days=payload.valid_days,
            current_period_end=payload.current_period_end,
            discount_until=payload.discount_until,
            memo=payload.memo,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/api/admin/billing/entitlements/{user_id}")
def revoke_entitlement_api(
    user_id: int,
    memo: Optional[str] = Query(None),
    _master: User = Depends(require_role(ROLE_MASTER)),
) -> Dict[str, Any]:
    """ユーザーの active entitlement を即時取り消す (Free へ降格)"""
    ok = entitlement_service.revoke_entitlement(user_id, memo=memo)
    if not ok:
        raise HTTPException(status_code=404, detail="No active entitlement for this user")
    return {"success": True}


@router.post("/api/admin/billing/sweep")
def run_sweep(
    _master: User = Depends(require_role(ROLE_MASTER)),
) -> Dict[str, Any]:
    """期限切れスイープを手動実行する (日次ジョブとは別にいつでも実行可)"""
    return entitlement_service.sweep_expired_entitlements()


# ---------------------------------------------------------------------------
# master: PDF アーカイブ メタデータ CRUD
# ---------------------------------------------------------------------------

@router.post("/api/admin/billing/pdf-archives", status_code=status.HTTP_201_CREATED)
def create_pdf_archive(
    payload: CreatePdfArchiveRequest,
    _master: User = Depends(require_role(ROLE_MASTER)),
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = session.execute(text("""
            INSERT INTO pro_pdf_archives
                (title, category, published_at, note_url, storage_provider,
                 bucket_name, object_key, file_size_bytes, visibility)
            VALUES (:title, :category, :published_at, :note_url, :provider,
                    :bucket, :key, :size, :visibility)
            RETURNING id
        """), {
            "title": payload.title, "category": payload.category,
            "published_at": payload.published_at, "note_url": payload.note_url,
            "provider": payload.storage_provider, "bucket": payload.bucket_name,
            "key": payload.object_key, "size": payload.file_size_bytes,
            "visibility": payload.visibility,
        }).fetchone()
        session.commit()
    return {"id": row[0]}


@router.get("/api/admin/billing/pdf-archives")
def list_pdf_archives_admin(
    _master: User = Depends(require_role(ROLE_MASTER)),
) -> List[Dict[str, Any]]:
    return _fetch_pdf_archives(include_inactive=True, include_storage=True)


@router.patch("/api/admin/billing/pdf-archives/{archive_id}")
def update_pdf_archive(
    archive_id: int,
    payload: UpdatePdfArchiveRequest,
    _master: User = Depends(require_role(ROLE_MASTER)),
) -> Dict[str, Any]:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    with SessionLocal() as session:
        result = session.execute(
            text(f"UPDATE pro_pdf_archives SET {set_clause} WHERE id = :id"),
            {**updates, "id": archive_id},
        )
        session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="PDF archive not found")
    return {"success": True}


# ---------------------------------------------------------------------------
# ログインユーザー: 自分のプラン状態
# ---------------------------------------------------------------------------

@router.get("/api/billing/me")
def my_plan(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """自分の現在プラン (フロントのプラン表示・アップグレード導線用)"""
    ent = entitlement_service.get_active_entitlement(user.id)
    return {
        "role": user.role,
        "plan_code": ent["plan_code"] if ent else "free",
        "entitlement_source": ent["entitlement_source"] if ent else "signup",
        "current_period_end": ent["current_period_end"] if ent else None,
        "discount_until": ent["discount_until"] if ent else None,
        "has_pro_access": entitlement_service.has_pro_access(user.id, role=user.role),
    }


# ---------------------------------------------------------------------------
# Pro: PDF アーカイブ閲覧
# ---------------------------------------------------------------------------

def _require_pro(user: User) -> None:
    """Pro 権限チェック (role では EconAlpha単体と区別できないため plan_code で判定)"""
    if not entitlement_service.has_pro_access(user.id, role=user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EconAlpha Pro plan is required for the PDF archive",
        )


def _fetch_pdf_archives(include_inactive: bool = False,
                        include_storage: bool = False) -> List[Dict[str, Any]]:
    where = "" if include_inactive else "WHERE is_active = TRUE"
    with SessionLocal() as session:
        rows = session.execute(text(f"""
            SELECT id, title, category, published_at, note_url,
                   storage_provider, bucket_name, object_key,
                   file_size_bytes, visibility, is_active, created_at
            FROM pro_pdf_archives
            {where}
            ORDER BY published_at DESC NULLS LAST, id DESC
        """)).fetchall()
    result = []
    for r in rows:
        item = {
            "id": r[0], "title": r[1], "category": r[2],
            "published_at": r[3].isoformat() if r[3] else None,
            "note_url": r[4],
            "file_size_bytes": r[8], "visibility": r[9],
            "is_active": r[10],
            "created_at": r[11].isoformat() if r[11] else None,
        }
        if include_storage:
            # object_key 等のストレージ内部情報は管理APIのみに含める
            item.update({
                "storage_provider": r[5], "bucket_name": r[6], "object_key": r[7],
            })
        result.append(item)
    return result


@router.get("/api/pro/pdf-archives")
def list_pdf_archives(user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """Pro: PDF アーカイブ一覧 (メタデータのみ。実体は署名URL経由)"""
    _require_pro(user)
    return _fetch_pdf_archives(include_inactive=False, include_storage=False)


@router.get("/api/pro/pdf-archives/{archive_id}/url")
def get_pdf_url(
    archive_id: int,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Pro: 短時間署名URLを発行する (public 固定URLは作らない — 計画書 Table 9)

    Object Storage が未設定の間は 503 を返す。
    LIGHTSAIL_BUCKET_* 環境変数を設定すれば追加実装なしで有効になる。
    """
    _require_pro(user)

    with SessionLocal() as session:
        row = session.execute(text("""
            SELECT bucket_name, object_key, title
            FROM pro_pdf_archives
            WHERE id = :id AND is_active = TRUE
        """), {"id": archive_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="PDF archive not found")
    bucket, object_key, title = row
    if not object_key:
        raise HTTPException(status_code=404, detail="This archive has no uploaded file yet")

    try:
        url, expires_in = generate_presigned_url(
            bucket_name=bucket, object_key=object_key
        )
    except ObjectStorageNotConfigured as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    return {"url": url, "expires_in": expires_in, "title": title}
