"""
Discord ニュースフィード API エンドポイント
"""

from fastapi import APIRouter, Query

try:
    from backend.core.database import get_db_connection
    from backend.services.discord.discord_news_listener import discord_news_listener
except ImportError:
    from core.database import get_db_connection
    from services.discord.discord_news_listener import discord_news_listener

router = APIRouter(prefix="/api/discord", tags=["Discord News"])


@router.get("/news")
def get_news(
    limit: int = Query(20, ge=1, le=100, description="取得件数"),
    offset: int = Query(0, ge=0, description="オフセット"),
):
    """最新ニュースを取得"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, message_id, channel_id, author_name,
                       content, content_ja,
                       embed_title, embed_description,
                       embed_title_ja, embed_description_ja,
                       published_at, created_at
                FROM discord_news
                ORDER BY published_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

            cur.execute("SELECT COUNT(*) FROM discord_news")
            total = cur.fetchone()[0]

    # datetime を ISO format 文字列に変換
    for row in rows:
        for key in ("published_at", "created_at"):
            if row.get(key):
                row[key] = row[key].isoformat()

    return {
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/news/status")
def get_status():
    """Discord リスナーの接続状態"""
    return discord_news_listener.get_status()
