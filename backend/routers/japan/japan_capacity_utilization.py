"""
Japan Capacity Utilization Router
稼働率指数 (Manufacturing Capacity Utilization) from METI
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

try:
    from backend.services.japan.japan_capacity_utilization_service import japan_capacity_utilization_service
except ImportError:
    from services.japan.japan_capacity_utilization_service import japan_capacity_utilization_service

router = APIRouter(prefix="/api/japan/capacity-utilization", tags=["Japan Capacity Utilization"])


@router.get("")
async def get_capacity_utilization_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get Japan Manufacturing Capacity Utilization data

    Data source: Ministry of Economy, Trade and Industry (METI)
    URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ngsm1j.xlsx

    Returns:
        - data: List of monthly capacity utilization values
        - latest: Most recent data point
        - cached: Whether data was served from cache
        - source: Data source (redis/meti/file)
        - last_updated: Last update timestamp
    """
    return japan_capacity_utilization_service.get_capacity_data(force_refresh=force_refresh)


@router.post("/refresh")
async def refresh_capacity_utilization_data() -> Dict[str, Any]:
    """Force refresh capacity utilization data from METI"""
    return japan_capacity_utilization_service.get_capacity_data(force_refresh=True)


@router.delete("/cache")
async def invalidate_capacity_utilization_cache() -> Dict[str, Any]:
    """Invalidate capacity utilization cache"""
    success = japan_capacity_utilization_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Cache invalidation failed"}


@router.get("/cache-status")
async def get_cache_status() -> Dict[str, Any]:
    """Get cache status for capacity utilization data"""
    return japan_capacity_utilization_service.get_cache_status()
