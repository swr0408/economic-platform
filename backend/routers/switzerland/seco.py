"""
SECO（スイス連邦経済省経済事務局）関連 APIルーター

提供データ:
- Consumer Climate（消費者景況感）
"""
from fastapi import APIRouter, Query

router = APIRouter(
    prefix="/api/switzerland/seco",
    tags=["switzerland", "consumer"]
)


@router.get("/")
async def seco_root():
    """SECO APIルート"""
    return {
        "message": "SECO (State Secretariat for Economic Affairs) API",
        "status": "Active",
        "available_endpoints": [
            "/consumer-sentiment - Consumer Climate"
        ]
    }


@router.get("/consumer-sentiment")
async def get_consumer_sentiment(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    SECO消費者景況感データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_consumer_sentiment_service import ch_consumer_sentiment_service

    return ch_consumer_sentiment_service.get_consumer_sentiment_data(force_refresh=force_refresh)


@router.get("/consumer-sentiment/latest")
async def get_consumer_sentiment_latest():
    """
    SECO消費者景況感 最新データを取得

    Returns:
        最新のSECO消費者景況感データ
    """
    from services.switzerland.ch_consumer_sentiment_service import ch_consumer_sentiment_service

    result = ch_consumer_sentiment_service.get_consumer_sentiment_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/consumer-sentiment/cache/status")
async def get_consumer_sentiment_cache_status():
    """SECO消費者景況感 キャッシュ状態を取得"""
    from services.switzerland.ch_consumer_sentiment_service import ch_consumer_sentiment_service

    return ch_consumer_sentiment_service.get_cache_status()


@router.delete("/consumer-sentiment/cache")
async def invalidate_consumer_sentiment_cache():
    """SECO消費者景況感 キャッシュを無効化"""
    from services.switzerland.ch_consumer_sentiment_service import ch_consumer_sentiment_service

    success = ch_consumer_sentiment_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
