"""
Japan IIP Forecast Router
鉱工業生産予測指数 API endpoints
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

try:
    from backend.services.japan.japan_iip_forecast_service import japan_iip_forecast_service
except ImportError:
    from services.japan.japan_iip_forecast_service import japan_iip_forecast_service

router = APIRouter(prefix="/api/japan/iip-forecast", tags=["Japan IIP Forecast"])


@router.get("")
async def get_iip_forecast_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get Japan IIP Forecast data (鉱工業生産予測指数)

    Data source: Ministry of Economy, Trade and Industry (METI)
    Excel URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ygzosm1je.xlsx
    PDF URL: https://www.meti.go.jp/statistics/tyo/iip/result/pdf/reference/rev_forecast.pdf

    Returns:
        - data: List of forecast data with item_name, this_month, next_month
        - forecast_month: Target month for this_month forecast
        - next_month: Target month for next_month forecast
        - revision_table: Correction values table from PDF
        - cached: Whether data was served from cache
        - source: Data source (redis/meti/file)
        - last_updated: Last update timestamp
        - pdf_reference: URL to PDF reference document
    """
    return japan_iip_forecast_service.get_iip_forecast_data(force_refresh=force_refresh)


@router.post("/refresh")
async def refresh_iip_forecast_data() -> Dict[str, Any]:
    """Force refresh IIP Forecast data from METI"""
    return japan_iip_forecast_service.get_iip_forecast_data(force_refresh=True)


@router.delete("/cache")
async def invalidate_iip_forecast_cache() -> Dict[str, Any]:
    """Invalidate IIP Forecast cache"""
    success = japan_iip_forecast_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Cache invalidation failed"}


@router.get("/cache-status")
async def get_cache_status() -> Dict[str, Any]:
    """Get cache status for IIP Forecast data"""
    return japan_iip_forecast_service.get_cache_status()
