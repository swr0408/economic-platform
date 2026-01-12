"""
ECB預金ファシリティ金利APIルーター

エンドポイント:
- GET /api/eurozone/ecb-rates - ECB金利データを取得
- GET /api/eurozone/ecb-rates/cache/status - キャッシュ状態を取得
- POST /api/eurozone/ecb-rates/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_rates_service import ecb_rates_service
except ImportError:
    from services.eurozone.ecb_rates_service import ecb_rates_service


router = APIRouter(
    prefix="/api/eurozone/ecb-rates",
    tags=["eurozone", "ecb-rates"]
)


@router.get("")
async def get_ecb_rates(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ECB預金ファシリティ金利データを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        ECB金利データ
    """
    result = ecb_rates_service.get_ecb_rates_data(force_refresh=refresh)

    if not result.get("data") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "data": result["data"],
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
        "meta": {
            "cached": result.get("cached", False),
            "source": result.get("source"),
            "last_updated": result.get("last_updated"),
            "count": len(result.get("data", []))
        }
    }


@router.get("/cache/status")
async def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_rates_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = ecb_rates_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
