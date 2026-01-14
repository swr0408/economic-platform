"""
Japan Retail Sales Router
API endpoints for Japan retail sales data (小売業販売額)
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.retail_sales_service import retail_sales_service
except ImportError:
    from services.japan.retail_sales_service import retail_sales_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Consumer"])


@router.get("/retail-sales")
async def get_retail_sales(
    force_refresh: bool = Query(False, description="Force refresh data")
):
    """
    Get Japan retail sales data (小売業販売額)

    Returns:
        - mom: Month-over-Month change (%)
        - yoy: Year-over-Year change (%)
        - next_release: Next release date info

    Data Sources (priority order):
        1. jp_retail_sales_history table - Long-term time series (base)
        2. e-Stat Excel - Latest 15 months (overwrites)
        3. FMP economic_calendar_events - Latest data (overwrites)

    Source: Ministry of Economy, Trade and Industry (METI)
    Release: Monthly, around 25th-31st at 08:50 JST
    """
    return retail_sales_service.get_retail_sales_data(force_refresh=force_refresh)


@router.post("/retail-sales/refresh")
async def refresh_retail_sales():
    """
    Force refresh Japan retail sales data

    This endpoint forces a refresh of the retail sales data cache,
    fetching the latest data from all sources.
    """
    return retail_sales_service.get_retail_sales_data(force_refresh=True)


@router.get("/retail-sales/cache-status")
async def get_cache_status():
    """
    Get cache status for retail sales data
    """
    return retail_sales_service.get_cache_status()


@router.delete("/retail-sales/cache")
async def invalidate_cache():
    """
    Invalidate retail sales data cache
    """
    success = retail_sales_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
