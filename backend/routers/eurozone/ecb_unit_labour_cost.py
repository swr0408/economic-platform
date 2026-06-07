"""
ECB Unit Labour Cost APIルーター

エンドポイント:
- GET /api/eurozone/unit-labour-cost - 労働コスト指数データを取得
- GET /api/eurozone/unit-labour-cost/cache/status - キャッシュ状態を取得
- POST /api/eurozone/unit-labour-cost/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_unit_labour_cost_service import ecb_unit_labour_cost_service
except ImportError:
    from services.eurozone.ecb_unit_labour_cost_service import ecb_unit_labour_cost_service


router = APIRouter(
    prefix="/api/eurozone/unit-labour-cost",
    tags=["eurozone", "unit-labour-cost"]
)


@router.get("")
def get_ecb_unit_labour_cost(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ECB労働コスト指数データを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        労働コスト指数データ（指数・前年比・前期比）
    """
    result = ecb_unit_labour_cost_service.get_ecb_unit_labour_cost_data(force_refresh=refresh)

    if not result.get("unit_labour_cost") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "unit_labour_cost": result.get("unit_labour_cost", []),
        "unit_labour_cost_yoy": result.get("unit_labour_cost_yoy", []),
        "unit_labour_cost_qoq": result.get("unit_labour_cost_qoq", []),
        "metadata": result.get("metadata", {}),
        "next_release": result.get("next_release"),
    }


@router.get("/cache/status")
def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_unit_labour_cost_service.get_cache_status()


@router.post("/cache/invalidate")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = ecb_unit_labour_cost_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
