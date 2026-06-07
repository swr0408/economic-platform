"""
価格転嫁率（中小企業庁）API Router

エンドポイント:
- GET /api/japan/price-pass-through-rate - 価格転嫁率データ取得
- GET /api/japan/price-pass-through-rate/cache-status - キャッシュステータス取得
- POST /api/japan/price-pass-through-rate/refresh - データ強制更新
- DELETE /api/japan/price-pass-through-rate/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.price_pass_through_rate_service import price_pass_through_rate_service
except ImportError:
    from services.japan.price_pass_through_rate_service import price_pass_through_rate_service

router = APIRouter(prefix="/api/japan/price-pass-through-rate", tags=["Japan - Price Pass-Through Rate"])


@router.get("")
def get_price_pass_through_rate_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """価格転嫁率データを取得"""
    try:
        result = price_pass_through_rate_service.get_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-status")
def get_cache_status():
    """キャッシュステータスを取得"""
    try:
        return price_pass_through_rate_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def refresh_data():
    """データを強制更新"""
    try:
        result = price_pass_through_rate_service.get_data(force_refresh=True)
        return {
            "status": "refreshed",
            "data_count": len(result.get("data", [])),
            "latest": result.get("latest"),
            "last_updated": result.get("last_updated"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
def invalidate_cache():
    """キャッシュを削除"""
    try:
        success = price_pass_through_rate_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
