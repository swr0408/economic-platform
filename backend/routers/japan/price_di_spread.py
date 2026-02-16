"""
価格DIスプレッド（Price DI Spread）API Router

販売価格判断DI - 仕入価格判断DI で計算
企業のマージン（採算）とインフレ転嫁状況を表す

エンドポイント:
- GET /api/japan/price-di-spread - 価格DIスプレッドデータ取得
- GET /api/japan/price-di-spread/cache-status - キャッシュステータス取得
- POST /api/japan/price-di-spread/refresh - データ強制更新
- DELETE /api/japan/price-di-spread/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.japan_price_di_spread_service import japan_price_di_spread_service
except ImportError:
    from services.japan.japan_price_di_spread_service import japan_price_di_spread_service

router = APIRouter(prefix="/api/japan/price-di-spread", tags=["Japan - Price DI Spread"])


@router.get("")
async def get_price_di_spread_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    価格DIスプレッドデータを取得

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        価格DIスプレッドデータ（四半期）
    """
    try:
        result = japan_price_di_spread_service.get_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-status")
async def get_cache_status():
    """
    キャッシュステータスを取得

    Returns:
        キャッシュの状態情報
    """
    try:
        return japan_price_di_spread_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_data():
    """
    データを強制更新

    Returns:
        更新後のデータ
    """
    try:
        result = japan_price_di_spread_service.get_data(force_refresh=True)
        return {
            "status": "refreshed",
            "data_count": len(result.get("data", [])),
            "latest": result.get("latest"),
            "last_updated": result.get("last_updated")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
async def invalidate_cache():
    """
    キャッシュを削除

    Returns:
        削除結果
    """
    try:
        success = japan_price_di_spread_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
