"""
ECB Labor Productivity APIルーター

エンドポイント:
- GET /api/eurozone/labor-productivity - 労働生産性データを取得
- GET /api/eurozone/labor-productivity/cache/status - キャッシュ状態を取得
- POST /api/eurozone/labor-productivity/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_labor_productivity_service import ecb_labor_productivity_service
except ImportError:
    from services.eurozone.ecb_labor_productivity_service import ecb_labor_productivity_service


router = APIRouter(
    prefix="/api/eurozone/labor-productivity",
    tags=["eurozone", "labor-productivity"]
)


@router.get("")
async def get_ecb_labor_productivity(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ECB労働生産性データを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        労働生産性データ（時間あたり・就業者あたり、前年比）
    """
    result = ecb_labor_productivity_service.get_ecb_labor_productivity_data(force_refresh=refresh)

    if not result.get("per_hour") and not result.get("per_person") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "per_hour": result.get("per_hour", []),
        "per_person": result.get("per_person", []),
        "per_hour_yoy": result.get("per_hour_yoy", []),
        "per_person_yoy": result.get("per_person_yoy", []),
        "metadata": result.get("metadata", {}),
        "next_release": result.get("next_release"),
    }


@router.get("/cache/status")
async def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_labor_productivity_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = ecb_labor_productivity_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
