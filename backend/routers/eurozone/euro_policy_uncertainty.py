"""
欧州経済政策不確実性指数 APIルーター

エンドポイント:
- GET /api/eurozone/policy-uncertainty - 政策不確実性指数データを取得
- GET /api/eurozone/policy-uncertainty/cache/status - キャッシュ状態を取得
- POST /api/eurozone/policy-uncertainty/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.euro_policy_uncertainty_service import euro_policy_uncertainty_service
except ImportError:
    from services.eurozone.euro_policy_uncertainty_service import euro_policy_uncertainty_service


router = APIRouter(
    prefix="/api/eurozone/policy-uncertainty",
    tags=["eurozone", "policy-uncertainty"]
)


@router.get("")
def get_euro_policy_uncertainty(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    欧州経済政策不確実性指数データを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        政策不確実性指数データ
    """
    result = euro_policy_uncertainty_service.get_euro_policy_uncertainty_data(force_refresh=refresh)

    if not result.get("data") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "data": result.get("data", []),
        "latest": result.get("latest"),
        "metadata": result.get("metadata", {}),
    }


@router.get("/cache/status")
def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return euro_policy_uncertainty_service.get_cache_status()


@router.post("/cache/invalidate")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = euro_policy_uncertainty_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
