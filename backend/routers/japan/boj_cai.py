"""
BOJ Consumption Activity Index (CAI) Router
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.boj_cai_service import boj_cai_service
except ImportError:
    from services.japan.boj_cai_service import boj_cai_service

router = APIRouter(
    prefix="/api/japan/boj-cai",
    tags=["japan", "consumption"]
)


@router.get("")
async def get_boj_cai(force_refresh: bool = Query(False, description="Force refresh from source")):
    """
    Get BOJ Consumption Activity Index data

    Returns:
        BOJ CAI data with nominal and real consumption activity indices
    """
    return boj_cai_service.get_cai_data(force_refresh=force_refresh)


@router.get("/chart")
async def get_boj_cai_chart(force_refresh: bool = Query(False, description="Force refresh from source")):
    """
    Get BOJ CAI data formatted for chart display

    Returns:
        BOJ CAI data with metadata for chart rendering
    """
    return boj_cai_service.get_chart_data(force_refresh=force_refresh)


@router.post("/refresh")
async def refresh_boj_cai():
    """
    Force refresh BOJ CAI data from source

    Returns:
        Updated BOJ CAI data
    """
    return boj_cai_service.get_cai_data(force_refresh=True)


@router.get("/cache-status")
async def get_boj_cai_cache_status():
    """
    Get BOJ CAI cache status

    Returns:
        Cache status information
    """
    return boj_cai_service.get_cache_status()


@router.delete("/cache")
async def invalidate_boj_cai_cache():
    """
    Invalidate BOJ CAI cache

    Returns:
        Result of cache invalidation
    """
    success = boj_cai_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Cache invalidation failed"}
