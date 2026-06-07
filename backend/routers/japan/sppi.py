"""
Japan SPPI (Services Producer Price Index) Router
API endpoints for Japan SPPI data (企業向けサービス価格指数)
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.japan_sppi_service import japan_sppi_service
except ImportError:
    from services.japan.japan_sppi_service import japan_sppi_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Price"])


@router.get("/sppi")
def get_sppi(
    force_refresh: bool = Query(False, description="Force refresh data")
):
    """
    Get Japan SPPI (Services Producer Price Index) data

    Returns:
        - index: Price index value
        - yoy: Year-over-Year change (%)
        - next_release: Next release date info

    Data Source: Bank of Japan (日本銀行)
    Release: Monthly, around 22nd-28th at 08:50 JST
    """
    return japan_sppi_service.get_sppi_data(force_refresh=force_refresh)


@router.post("/sppi/refresh")
def refresh_sppi():
    """
    Force refresh Japan SPPI data

    This endpoint forces a refresh of the SPPI data cache,
    fetching the latest data from BOJ.
    """
    return japan_sppi_service.get_sppi_data(force_refresh=True)


@router.get("/sppi/cache-status")
def get_cache_status():
    """
    Get cache status for SPPI data
    """
    return japan_sppi_service.get_cache_status()


@router.delete("/sppi/cache")
def invalidate_cache():
    """
    Invalidate SPPI data cache
    """
    success = japan_sppi_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
