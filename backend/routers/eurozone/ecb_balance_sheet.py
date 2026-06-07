"""
ECBバランスシートAPIルーター

エンドポイント:
- GET /api/eurozone/ecb-balance-sheet - ECBバランスシートデータを取得
- GET /api/eurozone/ecb-balance-sheet/cache/status - キャッシュ状態を取得
- POST /api/eurozone/ecb-balance-sheet/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_balance_sheet_service import ecb_balance_sheet_service
except ImportError:
    from services.eurozone.ecb_balance_sheet_service import ecb_balance_sheet_service


router = APIRouter(
    prefix="/api/eurozone/ecb-balance-sheet",
    tags=["eurozone", "ecb-balance-sheet"]
)


@router.get("")
def get_ecb_balance_sheet(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ECBバランスシート（総資産）データを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        ECBバランスシートデータ
    """
    result = ecb_balance_sheet_service.get_ecb_balance_sheet_data(force_refresh=refresh)

    if not result.get("data") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "data": result["data"],
        "latest": result.get("latest"),
        "meta": {
            "cached": result.get("cached", False),
            "source": result.get("source"),
            "last_updated": result.get("last_updated"),
            "count": len(result.get("data", []))
        }
    }


@router.get("/cache/status")
def get_cache_status():
    """キャッシュの状態を取得"""
    return ecb_balance_sheet_service.get_cache_status()


@router.post("/cache/invalidate")
def invalidate_cache():
    """キャッシュを無効化"""
    success = ecb_balance_sheet_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
