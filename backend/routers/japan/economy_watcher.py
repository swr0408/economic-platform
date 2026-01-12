"""
Japan Economy Watcher Router
API endpoints for Japan Economy Watcher Survey data (景気ウォッチャー調査)
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.economy_watcher_service import economy_watcher_service
except ImportError:
    from services.japan.economy_watcher_service import economy_watcher_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Economy Watcher"])


@router.get("/economy-watcher")
async def get_economy_watcher(
    force_refresh: bool = Query(False, description="Force refresh data from Cabinet Office")
):
    """
    Get Japan Economy Watcher Survey data (景気ウォッチャー調査)

    Returns both current conditions (現状判断) and outlook (先行き判断) data.

    Data items:
        - total: Total DI (合計)
        - household: Household-related DI (家計動向関連)
        - corporate: Corporate-related DI (企業動向関連)
        - employment: Employment-related DI (雇用関連)

    Query Parameters:
        - force_refresh: Force refresh data from Cabinet Office

    Source: Cabinet Office (内閣府)
    Release: Monthly, around 8th-14th
    """
    return economy_watcher_service.get_economy_watcher_data(force_refresh=force_refresh)


@router.get("/economy-watcher/current")
async def get_economy_watcher_current(
    force_refresh: bool = Query(False, description="Force refresh data from Cabinet Office")
):
    """
    Get Japan Economy Watcher Survey - Current Conditions (現状判断DI)

    Returns current economic sentiment data:
        - date: Month (YYYY-MM-01 format)
        - total: Total DI (合計)
        - household: Household-related DI (家計動向関連)
        - corporate: Corporate-related DI (企業動向関連)
        - employment: Employment-related DI (雇用関連)

    Query Parameters:
        - force_refresh: Force refresh data from Cabinet Office

    Source: Cabinet Office (内閣府)
    """
    return economy_watcher_service.get_current_data(force_refresh=force_refresh)


@router.get("/economy-watcher/outlook")
async def get_economy_watcher_outlook(
    force_refresh: bool = Query(False, description="Force refresh data from Cabinet Office")
):
    """
    Get Japan Economy Watcher Survey - Outlook (先行き判断DI)

    Returns economic outlook data:
        - date: Month (YYYY-MM-01 format)
        - total: Total DI (合計)
        - household: Household-related DI (家計動向関連)
        - corporate: Corporate-related DI (企業動向関連)
        - employment: Employment-related DI (雇用関連)

    Query Parameters:
        - force_refresh: Force refresh data from Cabinet Office

    Source: Cabinet Office (内閣府)
    """
    return economy_watcher_service.get_outlook_data(force_refresh=force_refresh)


@router.post("/economy-watcher/refresh")
async def refresh_economy_watcher():
    """
    Force refresh Japan Economy Watcher Survey data from Cabinet Office

    This endpoint forces a refresh of the Economy Watcher data cache,
    fetching the latest data from Cabinet Office.
    """
    return economy_watcher_service.get_economy_watcher_data(force_refresh=True)


@router.get("/economy-watcher/cache-status")
async def get_cache_status():
    """
    Get cache status for Economy Watcher data
    """
    return economy_watcher_service.get_cache_status()


@router.delete("/economy-watcher/cache")
async def invalidate_cache():
    """
    Invalidate Economy Watcher data cache
    """
    success = economy_watcher_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
