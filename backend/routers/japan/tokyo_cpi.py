"""
Japan Tokyo CPI Router
API endpoints for Japan Tokyo CPI data (東京都区部消費者物価指数)
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.japan_tokyo_cpi_service import japan_tokyo_cpi_service
except ImportError:
    from services.japan.japan_tokyo_cpi_service import japan_tokyo_cpi_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Price"])


@router.get("/tokyo-cpi")
async def get_tokyo_cpi(
    force_refresh: bool = Query(False, description="Force refresh data")
):
    """
    Get Japan Tokyo CPI data (東京都区部消費者物価指数)

    Tokyo CPI is a leading indicator released ahead of National CPI.

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
    Release: Monthly, around 24th-28th at 08:30 JST (ahead of National CPI)
    """
    return japan_tokyo_cpi_service.get_tokyo_cpi_data(force_refresh=force_refresh)


@router.post("/tokyo-cpi/refresh")
async def refresh_tokyo_cpi():
    """
    Force refresh Japan Tokyo CPI data

    This endpoint forces a refresh of the Tokyo CPI data cache,
    fetching the latest data from e-Stat API.
    """
    return japan_tokyo_cpi_service.get_tokyo_cpi_data(force_refresh=True)


@router.get("/tokyo-cpi/cache-status")
async def get_cache_status():
    """
    Get cache status for Tokyo CPI data
    """
    return japan_tokyo_cpi_service.get_cache_status()


@router.delete("/tokyo-cpi/cache")
async def invalidate_cache():
    """
    Invalidate Tokyo CPI data cache
    """
    success = japan_tokyo_cpi_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
