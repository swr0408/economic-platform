"""
TSMC月次売上高 APIエンドポイント

GET  /api/market/tsmc/revenue       - データ取得
GET  /api/market/tsmc/revenue/cache  - キャッシュ状態
DELETE /api/market/tsmc/revenue/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.market.tsmc_revenue_service import tsmc_revenue_service

router = APIRouter(prefix="/api/market/tsmc", tags=["Market - TSMC"])


@router.get("/revenue")
def get_tsmc_revenue(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """TSMC月次売上高データを取得"""
    result = tsmc_revenue_service.get_data(force_refresh=force_refresh)
    return JSONResponse(content=result)


@router.get("/revenue/cache")
def get_tsmc_revenue_cache_status():
    """TSMC月次売上高のキャッシュ状態"""
    return tsmc_revenue_service.get_cache_status()


@router.delete("/revenue/cache")
def invalidate_tsmc_revenue_cache():
    """TSMC月次売上高のキャッシュを無効化"""
    success = tsmc_revenue_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed"}
