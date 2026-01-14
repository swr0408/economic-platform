"""
Japan Scheduled Wage Router
API endpoints for Japan scheduled wage data (所定内給与)
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.scheduled_wage_service import scheduled_wage_service
except ImportError:
    from services.japan.scheduled_wage_service import scheduled_wage_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Employment"])


@router.get("/scheduled-wage")
async def get_scheduled_wage(
    force_refresh: bool = Query(False, description="Force refresh data")
):
    """
    Get Japan scheduled wage data (所定内給与)

    Returns:
        - scheduled_wage: Scheduled wage YoY change (%)
        - general: General worker scheduled wage YoY (%)
        - part_time: Part-time worker scheduled wage YoY (%)
        - next_release: Next release date info

    Data Source: e-Stat 毎月勤労統計調査・付表
    Release: Monthly, around 5th-10th at 08:30 JST
    """
    return scheduled_wage_service.get_scheduled_wage_data(force_refresh=force_refresh)


@router.post("/scheduled-wage/refresh")
async def refresh_scheduled_wage():
    """
    Force refresh Japan scheduled wage data

    This endpoint forces a refresh of the scheduled wage data cache,
    fetching the latest data from e-Stat.
    """
    return scheduled_wage_service.get_scheduled_wage_data(force_refresh=True)


@router.get("/scheduled-wage/cache-status")
async def get_cache_status():
    """
    Get cache status for scheduled wage data
    """
    return scheduled_wage_service.get_cache_status()


@router.delete("/scheduled-wage/cache")
async def invalidate_cache():
    """
    Invalidate scheduled wage data cache
    """
    success = scheduled_wage_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
