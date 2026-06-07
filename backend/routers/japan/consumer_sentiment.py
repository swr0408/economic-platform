"""
Japan Consumer Sentiment Router
API endpoints for Japan consumer attitude index data (消費動向調査)
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.consumer_sentiment_service import consumer_sentiment_service
except ImportError:
    from services.japan.consumer_sentiment_service import consumer_sentiment_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Consumer Sentiment"])


@router.get("/consumer-sentiment")
def get_consumer_sentiment(
    force_refresh: bool = Query(False, description="Force refresh data from e-Stat")
):
    """
    Get Japan consumer sentiment data (消費動向調査 - 消費者態度指数)

    Returns:
        - date: Month (YYYY-MM-01 format)
        - cci: Consumer Confidence Index (消費者態度指数)
        - livelihood: Overall livelihood (暮らし向き)
        - income: Income growth (収入の増え方)
        - employment: Employment environment (雇用環境)
        - durable_goods: Willingness to buy durable goods (耐久消費財の買い時判断)

    Query Parameters:
        - force_refresh: Force refresh data from e-Stat API

    Source: Cabinet Office, Economic and Social Research Institute (e-Stat)
    Release: Monthly, around end of month at 14:00 JST
    """
    return consumer_sentiment_service.get_consumer_sentiment_data(force_refresh=force_refresh)


@router.get("/consumer-sentiment/chart")
def get_consumer_sentiment_chart(
    force_refresh: bool = Query(False, description="Force refresh data from e-Stat")
):
    """
    Get Japan consumer sentiment data formatted for chart display

    Returns chart-ready data with metadata for visualization
    """
    return consumer_sentiment_service.get_chart_data(force_refresh=force_refresh)


@router.post("/consumer-sentiment/refresh")
def refresh_consumer_sentiment():
    """
    Force refresh Japan consumer sentiment data from e-Stat API

    This endpoint forces a refresh of the consumer sentiment data cache,
    fetching the latest data from e-Stat.
    """
    return consumer_sentiment_service.get_consumer_sentiment_data(force_refresh=True)


@router.get("/consumer-sentiment/cache-status")
def get_cache_status():
    """
    Get cache status for consumer sentiment data
    """
    return consumer_sentiment_service.get_cache_status()


@router.delete("/consumer-sentiment/cache")
def invalidate_cache():
    """
    Invalidate consumer sentiment data cache
    """
    success = consumer_sentiment_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
