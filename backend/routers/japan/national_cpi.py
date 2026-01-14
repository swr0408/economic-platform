"""
Japan National CPI Router
API endpoints for Japan National CPI data (全国消費者物価指数)
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.japan_national_cpi_service import japan_national_cpi_service
except ImportError:
    from services.japan.japan_national_cpi_service import japan_national_cpi_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Price"])


@router.get("/national-cpi")
async def get_national_cpi(
    force_refresh: bool = Query(False, description="Force refresh data")
):
    """
    Get Japan National CPI data (全国消費者物価指数)

    Returns:
        - yoy: Year-over-Year change (%) for All Items
        - mom: Month-over-Month change (%) for All Items
        - core_yoy: Core CPI YoY (生鮮食品を除く総合)
        - core_mom: Core CPI MoM
        - core_core_yoy: Core-Core CPI YoY (食料及びエネルギーを除く総合)
        - core_core_mom: Core-Core CPI MoM
        - index: Price index
        - next_release: Next release date info

    Data Source: Statistics Bureau of Japan (総務省統計局)
    Release: Monthly, around 18th-21st at 08:30 JST
    """
    return japan_national_cpi_service.get_national_cpi_data(force_refresh=force_refresh)


@router.post("/national-cpi/refresh")
async def refresh_national_cpi():
    """
    Force refresh Japan National CPI data

    This endpoint forces a refresh of the National CPI data cache,
    fetching the latest data from e-Stat API.
    """
    return japan_national_cpi_service.get_national_cpi_data(force_refresh=True)


@router.get("/national-cpi/cache-status")
async def get_cache_status():
    """
    Get cache status for National CPI data
    """
    return japan_national_cpi_service.get_cache_status()


@router.delete("/national-cpi/cache")
async def invalidate_cache():
    """
    Invalidate National CPI data cache
    """
    success = japan_national_cpi_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
