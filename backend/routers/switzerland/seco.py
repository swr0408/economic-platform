"""
SECO（スイス連邦経済省経済事務局）関連 APIルーター

提供データ:
- Consumer Climate（消費者景況感）
- GDP Growth Rate（GDP成長率）
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
            "/consumer-sentiment - Consumer Climate",
            "/growth-rate - GDP Growth Rate",
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


# =============================================================================
# GDP成長率（Growth Rate）
# =============================================================================

@router.get("/growth-rate")
async def get_growth_rate(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイスGDP成長率データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_growth_rate_service import ch_growth_rate_service

    return ch_growth_rate_service.get_ch_growth_rate_data(force_refresh=force_refresh)


@router.get("/growth-rate/latest")
async def get_growth_rate_latest():
    """
    スイスGDP成長率 最新データを取得

    Returns:
        最新のスイスGDP成長率データ
    """
    from services.switzerland.ch_growth_rate_service import ch_growth_rate_service

    result = ch_growth_rate_service.get_ch_growth_rate_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/growth-rate/cache/status")
async def get_growth_rate_cache_status():
    """スイスGDP成長率 キャッシュ状態を取得"""
    from services.switzerland.ch_growth_rate_service import ch_growth_rate_service

    return ch_growth_rate_service.get_cache_status()


@router.delete("/growth-rate/cache")
async def invalidate_growth_rate_cache():
    """スイスGDP成長率 キャッシュを無効化"""
    from services.switzerland.ch_growth_rate_service import ch_growth_rate_service

    success = ch_growth_rate_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
