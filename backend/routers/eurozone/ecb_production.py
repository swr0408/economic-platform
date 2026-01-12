"""
ECB鉱工業生産APIルーター

エンドポイント:
- GET /api/eurozone/ecb-production - ECB鉱工業生産データを取得
- GET /api/eurozone/ecb-production/cache/status - キャッシュ状態を取得
- POST /api/eurozone/ecb-production/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_production_service import ecb_production_service
except ImportError:
    from services.eurozone.ecb_production_service import ecb_production_service


router = APIRouter(
    prefix="/api/eurozone/ecb-production",
    tags=["eurozone", "ecb-production"]
)


@router.get("")
async def get_ecb_production(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ECB鉱工業生産データを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        ECB鉱工業生産データ（WDA指数、前月比、前年比）
    """
    result = ecb_production_service.get_ecb_production_data(force_refresh=refresh)

    if not result.get("production_wda") and not result.get("mom_change") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "production_wda": result.get("production_wda", []),
        "mom_change": result.get("mom_change", []),
        "yoy_change": result.get("yoy_change", []),
        "metadata": result.get("metadata", {}),
    }


@router.get("/cache/status")
async def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_production_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = ecb_production_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
