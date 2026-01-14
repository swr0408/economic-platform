"""
Japan CGPI (Corporate Goods Price Index) Router
API endpoints for Japan CGPI data (企業物価指数)
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.japan_cgpi_service import japan_cgpi_service
except ImportError:
    from services.japan.japan_cgpi_service import japan_cgpi_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Price"])


@router.get("/cgpi")
async def get_cgpi(
    force_refresh: bool = Query(False, description="Force refresh data")
):
    """
    Get Japan CGPI (Corporate Goods Price Index) data

    Returns:
        - index: Price index value
        - yoy: Year-over-Year change (%)
        - mom: Month-over-Month change (%)
        - next_release: Next release date info

    Data Source: Bank of Japan (日本銀行)
    Release: Monthly, around 10th-18th at 08:50 JST
    """
    return japan_cgpi_service.get_cgpi_data(force_refresh=force_refresh)


@router.post("/cgpi/refresh")
async def refresh_cgpi():
    """
    Force refresh Japan CGPI data

    This endpoint forces a refresh of the CGPI data cache,
    fetching the latest data from BOJ.
    """
    return japan_cgpi_service.get_cgpi_data(force_refresh=True)


@router.get("/cgpi/cache-status")
async def get_cache_status():
    """
    Get cache status for CGPI data
    """
    return japan_cgpi_service.get_cache_status()


@router.delete("/cgpi/cache")
async def invalidate_cache():
    """
    Invalidate CGPI data cache
    """
    success = japan_cgpi_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
