"""
ヘッドライン API エンドポイント
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

try:
    from backend.core.auth.dependencies import require_role
    from backend.core.auth.models import ROLE_MASTER
    from backend.services.headlines.headlines_service import (
        get_headlines, get_headline_by_id, save_headline, unsave_headline,
        create_manual_headline,
        get_categories, create_category, update_category, delete_category,
        seed_country_categories,
        get_read_marker, set_read_marker, clear_read_marker,
        reorder_saved_headlines, reorder_sidebar_entries,
    )
    from backend.services.headlines.translation_worker import translation_worker
    from backend.services.discord.discord_news_listener import discord_news_listener
    from backend.scheduler.headlines_rss_scheduler import headlines_rss_scheduler
except ImportError:
    from core.auth.dependencies import require_role
    from core.auth.models import ROLE_MASTER
    from services.headlines.headlines_service import (
        get_headlines, get_headline_by_id, save_headline, unsave_headline,
        create_manual_headline,
        get_categories, create_category, update_category, delete_category,
        seed_country_categories,
        get_read_marker, set_read_marker, clear_read_marker,
        reorder_saved_headlines, reorder_sidebar_entries,
    )
    from services.headlines.translation_worker import translation_worker
    from services.discord.discord_news_listener import discord_news_listener
    from scheduler.headlines_rss_scheduler import headlines_rss_scheduler

# master ロール要求の依存オブジェクト (ファクトリを一度呼んで使い回す)
_require_master = require_role(ROLE_MASTER)

router = APIRouter(prefix="/api", tags=["Headlines"])

# special または master のみ閲覧可 (FinancialJuice 由来は special 以上)
_require_special_or_master = require_role("special", ROLE_MASTER)


# ========== Headlines ==========

@router.get("/headlines")
def api_get_headlines(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None),
    roughCategory: Optional[str] = Query(None),
    speaker: Optional[str] = Query(None),
    savedOnly: bool = Query(False),
    savedCategoryName: Optional[str] = Query(None),
    savedCategoryId: Optional[int] = Query(None),
    savedCategoryPrefix: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    q: Optional[str] = Query(None),
    _user=Depends(_require_special_or_master),
):
    """ヘッドライン一覧 (special/master 限定)"""
    return get_headlines(
        limit=limit, offset=offset, source=source,
        rough_category=roughCategory, speaker=speaker,
        saved_only=savedOnly, saved_category_name=savedCategoryName,
        saved_category_id=savedCategoryId,
        saved_category_prefix=savedCategoryPrefix,
        date_from=date_from, date_to=date_to, q=q,
    )


# ========== 既読マーカー「ここまで見た」(master 限定) ==========
# NOTE: /headlines/{headline_id} より先に定義すること (パスマッチ順)

class ReadMarkerRequest(BaseModel):
    headlineId: int


@router.get("/headlines/read-marker")
def api_get_read_marker(user=Depends(_require_master)):
    """既読マーカー取得 (master 限定)"""
    return {"marker": get_read_marker(user.id)}


@router.put("/headlines/read-marker")
def api_set_read_marker(body: ReadMarkerRequest, user=Depends(_require_master)):
    """既読マーカー設定 (master 限定)"""
    result = set_read_marker(user.id, body.headlineId)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/headlines/read-marker")
def api_clear_read_marker(user=Depends(_require_master)):
    """既読マーカー解除 (master 限定)"""
    clear_read_marker(user.id)
    return {"success": True}


class SidebarOrderEntry(BaseModel):
    type: str  # 'saved' | 'category'
    id: int
    sortOrder: int


class SidebarOrderRequest(BaseModel):
    entries: list[SidebarOrderEntry]


@router.put("/headlines/sidebar-order")
def api_reorder_sidebar_entries(body: SidebarOrderRequest, _master=Depends(_require_master)):
    """サイドバーセクション内の表示順を保存 (master 限定)"""
    return reorder_sidebar_entries([e.model_dump() for e in body.entries])


@router.get("/headlines/{headline_id}")
def api_get_headline(headline_id: int, _user=Depends(_require_special_or_master)):
    """ヘッドライン詳細 (special/master 限定)"""
    result = get_headline_by_id(headline_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Headline not found")
    return result


class ManualHeadlineRequest(BaseModel):
    content: str
    roughCategory: Optional[str] = None
    categoryIds: list[int] = []
    newCategoryName: Optional[str] = None
    note: Optional[str] = None
    isPublicVisible: bool = False
    speakerName: Optional[str] = None
    organization: Optional[str] = None
    externalLink: Optional[str] = None


@router.post("/headlines/manual")
def api_create_manual_headline(
    body: ManualHeadlineRequest,
    _master=Depends(_require_master),
):
    """ヘッドラインを手動作成してカテゴリに保存 (master 限定)"""
    result = create_manual_headline(
        content=body.content,
        rough_category=body.roughCategory,
        category_ids=body.categoryIds,
        new_category_name=body.newCategoryName,
        note=body.note,
        is_public_visible=body.isPublicVisible,
        speaker_name=body.speakerName,
        organization=body.organization,
        external_link=body.externalLink,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class SaveRequest(BaseModel):
    categoryIds: list[int] = []
    newCategoryName: Optional[str] = None
    note: Optional[str] = None
    isPublicVisible: bool = False


@router.post("/headlines/{headline_id}/save")
def api_save_headline(
    headline_id: int,
    body: SaveRequest,
    _master=Depends(_require_master),
):
    """ヘッドラインを保存 (master 限定)"""
    result = save_headline(
        headline_id=headline_id,
        category_ids=body.categoryIds,
        new_category_name=body.newCategoryName,
        note=body.note,
        is_public_visible=body.isPublicVisible,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/headlines/{headline_id}/save/{saved_id}")
def api_unsave_headline(
    headline_id: int,
    saved_id: int,
    _master=Depends(_require_master),
):
    """保存解除 (master 限定)"""
    success = unsave_headline(saved_id)
    if not success:
        raise HTTPException(status_code=404, detail="Saved record not found")
    return {"success": True}


@router.post("/headlines/{headline_id}/retranslate")
def api_retranslate(headline_id: int, _master=Depends(_require_master)):
    """再翻訳 (master 限定)。即時翻訳して結果を返す。

    成功時 ``{"success": True, "status": "done", "headline_ja": ...}``、
    翻訳 API 失敗時は ``{"success": False, "status": "pending"}`` を返し、
    バックグラウンドワーカーが後続で再試行する。
    """
    return translation_worker.retranslate(headline_id)


# ========== Categories (master 限定) ==========

@router.get("/categories")
def api_get_categories(_master=Depends(_require_master)):
    """カテゴリ一覧 (master 限定)"""
    return get_categories()


class CategoryRequest(BaseModel):
    name: str
    color: str = "#3b82f6"
    parent_id: Optional[int] = None


@router.post("/categories")
def api_create_category(body: CategoryRequest, _master=Depends(_require_master)):
    """カテゴリ作成 (master 限定)。

    同名カテゴリは「別の親の下なら作成可」。同じ親の下に同名がある場合のみ 409 を返す。
    """
    result = create_category(name=body.name, color=body.color, parent_id=body.parent_id)
    if result.get("error"):
        raise HTTPException(status_code=409, detail=result["error"])
    return result


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


@router.patch("/categories/{category_id}")
def api_update_category(
    category_id: int,
    body: CategoryUpdateRequest,
    _master=Depends(_require_master),
):
    """カテゴリ更新 (master 限定)"""
    try:
        success = update_category(category_id, name=body.name, color=body.color, sort_order=body.sort_order)
    except ValueError as e:
        # 同名衝突 (UNIQUE 違反) は作成時と同様 409 で返す
        raise HTTPException(status_code=409, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"success": True}


class HeadlineOrderRequest(BaseModel):
    savedIds: list[int]


@router.put("/categories/{category_id}/headline-order")
def api_reorder_saved_headlines(
    category_id: int,
    body: HeadlineOrderRequest,
    _master=Depends(_require_master),
):
    """カテゴリ内の保存ヘッドラインを並び替え (master 限定)"""
    return reorder_saved_headlines(category_id, body.savedIds)


@router.delete("/categories/{category_id}")
def api_delete_category(category_id: int, _master=Depends(_require_master)):
    """カテゴリ削除 (master 限定)"""
    success = delete_category(category_id)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"success": True}


# ========== Admin (master ロール限定) ==========

@router.post("/admin/rss-backfill/run")
def api_rss_run(_master=Depends(_require_master)):
    """RSS手動実行 (master 限定)"""
    return headlines_rss_scheduler.run_now()


@router.get("/admin/rss-backfill/logs")
def api_rss_logs(
    limit: int = Query(20, ge=1, le=100),
    _master=Depends(_require_master),
):
    """RSS取得ログ (master 限定)"""
    return headlines_rss_scheduler.get_logs(limit)


@router.get("/admin/discord/status")
def api_discord_status(_master=Depends(_require_master)):
    """Discord接続状態 (master 限定)"""
    return discord_news_listener.get_status()


@router.get("/admin/status")
def api_admin_status(_master=Depends(_require_master)):
    """全体ステータス (master 限定)"""
    return {
        "discord": discord_news_listener.get_status(),
        "rss": headlines_rss_scheduler.get_status(),
        "translation": translation_worker.get_status(),
    }


@router.post("/admin/seed-categories")
def api_seed_categories(_master=Depends(_require_master)):
    """各国カテゴリの初期データ投入 (master 限定)"""
    return seed_country_categories()
