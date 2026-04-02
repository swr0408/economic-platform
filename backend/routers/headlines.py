"""
ヘッドライン API エンドポイント
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

try:
    from backend.services.headlines.headlines_service import (
        get_headlines, get_headline_by_id, save_headline, unsave_headline,
        get_categories, create_category, update_category, delete_category,
    )
    from backend.services.headlines.translation_worker import translation_worker
    from backend.services.discord.discord_news_listener import discord_news_listener
    from backend.scheduler.headlines_rss_scheduler import headlines_rss_scheduler
except ImportError:
    from services.headlines.headlines_service import (
        get_headlines, get_headline_by_id, save_headline, unsave_headline,
        get_categories, create_category, update_category, delete_category,
    )
    from services.headlines.translation_worker import translation_worker
    from services.discord.discord_news_listener import discord_news_listener
    from scheduler.headlines_rss_scheduler import headlines_rss_scheduler

router = APIRouter(prefix="/api", tags=["Headlines"])


# ========== Headlines ==========

@router.get("/headlines")
def api_get_headlines(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None),
    roughCategory: Optional[str] = Query(None),
    speaker: Optional[str] = Query(None),
    savedOnly: bool = Query(False),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    q: Optional[str] = Query(None),
):
    """ヘッドライン一覧"""
    return get_headlines(
        limit=limit, offset=offset, source=source,
        rough_category=roughCategory, speaker=speaker,
        saved_only=savedOnly, date_from=date_from, date_to=date_to, q=q,
    )


@router.get("/headlines/{headline_id}")
def api_get_headline(headline_id: int):
    """ヘッドライン詳細"""
    result = get_headline_by_id(headline_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Headline not found")
    return result


class SaveRequest(BaseModel):
    categoryIds: list[int] = []
    newCategoryName: Optional[str] = None
    note: Optional[str] = None


@router.post("/headlines/{headline_id}/save")
def api_save_headline(headline_id: int, body: SaveRequest):
    """ヘッドラインを保存"""
    result = save_headline(
        headline_id=headline_id,
        category_ids=body.categoryIds,
        new_category_name=body.newCategoryName,
        note=body.note,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/headlines/{headline_id}/save/{saved_id}")
def api_unsave_headline(headline_id: int, saved_id: int):
    """保存解除"""
    success = unsave_headline(saved_id)
    if not success:
        raise HTTPException(status_code=404, detail="Saved record not found")
    return {"success": True}


@router.post("/headlines/{headline_id}/retranslate")
def api_retranslate(headline_id: int):
    """再翻訳"""
    translation_worker.retranslate(headline_id)
    return {"success": True}


# ========== Categories ==========

@router.get("/categories")
def api_get_categories():
    """カテゴリ一覧"""
    return get_categories()


class CategoryRequest(BaseModel):
    name: str
    color: str = "#3b82f6"


@router.post("/categories")
def api_create_category(body: CategoryRequest):
    """カテゴリ作成"""
    return create_category(name=body.name, color=body.color)


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


@router.patch("/categories/{category_id}")
def api_update_category(category_id: int, body: CategoryUpdateRequest):
    """カテゴリ更新"""
    success = update_category(category_id, name=body.name, color=body.color, sort_order=body.sort_order)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"success": True}


@router.delete("/categories/{category_id}")
def api_delete_category(category_id: int):
    """カテゴリ削除"""
    success = delete_category(category_id)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"success": True}


# ========== Admin ==========

@router.post("/admin/rss-backfill/run")
def api_rss_run():
    """RSS手動実行"""
    return headlines_rss_scheduler.run_now()


@router.get("/admin/rss-backfill/logs")
def api_rss_logs(limit: int = Query(20, ge=1, le=100)):
    """RSS取得ログ"""
    return headlines_rss_scheduler.get_logs(limit)


@router.get("/admin/discord/status")
def api_discord_status():
    """Discord接続状態"""
    return discord_news_listener.get_status()


@router.get("/admin/status")
def api_admin_status():
    """全体ステータス"""
    return {
        "discord": discord_news_listener.get_status(),
        "rss": headlines_rss_scheduler.get_status(),
        "translation": translation_worker.get_status(),
    }
