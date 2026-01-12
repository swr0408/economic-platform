"""
ECB小売売上高 APIルーター

エンドポイント:
- GET /api/eurozone/retail-trade - 小売売上高データを取得
- GET /api/eurozone/retail-trade/cache/status - キャッシュ状態を取得
- POST /api/eurozone/retail-trade/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_retail_trade_service import ecb_retail_trade_service
except ImportError:
    from services.eurozone.ecb_retail_trade_service import ecb_retail_trade_service


router = APIRouter(
    prefix="/api/eurozone/retail-trade",
    tags=["eurozone", "retail-trade"]
)


@router.get("")
async def get_ecb_retail_trade(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ECB小売売上高データを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        小売売上高データ（前月比・前年比）
    """
    result = ecb_retail_trade_service.get_ecb_retail_trade_data(force_refresh=refresh)

    if not result.get("retail_yoy") and not result.get("retail_mom") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "retail_yoy": result.get("retail_yoy", []),
        "retail_mom": result.get("retail_mom", []),
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
    return ecb_retail_trade_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = ecb_retail_trade_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
