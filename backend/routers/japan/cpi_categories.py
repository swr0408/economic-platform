"""
Japan CPI 10 Major Categories Router
API endpoints for Japan CPI 10 major categories data (10大費目)
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.japan_cpi_categories_service import (
        japan_cpi_categories_service,
    )
except ImportError:
    from services.japan.japan_cpi_categories_service import japan_cpi_categories_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Price"])


@router.get("/cpi-categories")
async def get_cpi_categories(
    force_refresh: bool = Query(False, description="Force refresh data")
):
    """
    Get Japan CPI 10 major categories data (10大費目)

    Returns current and previous month data for:
        - 食料 (Food)
        - 住居 (Housing)
        - 光熱・水道 (Fuel, light & water charges)
        - 家具・家事用品 (Furniture & household utensils)
        - 被服及び履物 (Clothes & footwear)
        - 保健医療 (Medical care)
        - 交通・通信 (Transportation & communication)
        - 教育 (Education)
        - 教養娯楽 (Culture & recreation)
        - 諸雑費 (Miscellaneous)

    Query Parameters:
        - force_refresh: Force refresh data from e-Stat API

    Data Source: Statistics Bureau of Japan (総務省統計局)
    Release: Same as National CPI (monthly, around 18th-21st at 08:30 JST)
    """
    return japan_cpi_categories_service.get_cpi_categories_data(
        force_refresh=force_refresh
    )


@router.post("/cpi-categories/refresh")
async def refresh_cpi_categories():
    """
    Force refresh Japan CPI 10 major categories data

    This endpoint forces a refresh of the CPI categories data cache,
    fetching the latest data from e-Stat API.
    """
    return japan_cpi_categories_service.get_cpi_categories_data(force_refresh=True)


@router.get("/cpi-categories/cache-status")
async def get_cache_status():
    """
    Get cache status for CPI categories data
    """
    return japan_cpi_categories_service.get_cache_status()


@router.delete("/cpi-categories/cache")
async def invalidate_cache():
    """
    Invalidate CPI categories data cache
    """
    success = japan_cpi_categories_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache",
    }
