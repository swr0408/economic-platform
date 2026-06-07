"""
貿易収支 API Router

エンドポイント:
- GET /api/japan/balance-of-trade - 貿易収支データ取得（単位: 億円）
- GET /api/japan/balance-of-trade/cache-status - キャッシュステータス取得
- POST /api/japan/balance-of-trade/refresh - データ強制更新
- DELETE /api/japan/balance-of-trade/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.japan_balance_of_trade_service import japan_balance_of_trade_service
except ImportError:
    from services.japan.japan_balance_of_trade_service import japan_balance_of_trade_service

router = APIRouter(prefix="/api/japan/balance-of-trade", tags=["Japan - Balance of Trade"])


@router.get("")
def get_balance_of_trade_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    貿易収支データを取得

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        貿易収支データ（月次、単位: 億円）
    """
    try:
        result = japan_balance_of_trade_service.get_balance_of_trade_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-status")
def get_cache_status():
    """
    キャッシュステータスを取得

    Returns:
        キャッシュの状態情報
    """
    try:
        return japan_balance_of_trade_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def refresh_data():
    """
    データを強制更新

    Returns:
        更新後のデータ
    """
    try:
        result = japan_balance_of_trade_service.get_balance_of_trade_data(force_refresh=True)
        return {
            "status": "refreshed",
            "data_count": len(result.get("data", [])),
            "latest": result.get("latest"),
            "last_updated": result.get("last_updated")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
def invalidate_cache():
    """
    キャッシュを削除

    Returns:
        削除結果
    """
    try:
        success = japan_balance_of_trade_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
