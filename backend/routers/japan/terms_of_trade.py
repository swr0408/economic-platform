"""
交易条件（Terms of Trade）API Router

エンドポイント:
- GET /api/japan/terms-of-trade - 交易条件データ取得
- GET /api/japan/terms-of-trade/cache-status - キャッシュステータス取得
- POST /api/japan/terms-of-trade/refresh - データ強制更新
- DELETE /api/japan/terms-of-trade/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.japan_terms_of_trade_service import japan_terms_of_trade_service
except ImportError:
    from services.japan.japan_terms_of_trade_service import japan_terms_of_trade_service

router = APIRouter(prefix="/api/japan/terms-of-trade", tags=["Japan - Terms of Trade"])


@router.get("")
def get_terms_of_trade_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    交易条件データを取得

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        交易条件データ（月次）
    """
    try:
        result = japan_terms_of_trade_service.get_data(force_refresh=force_refresh)
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
        return japan_terms_of_trade_service.get_cache_status()
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
        result = japan_terms_of_trade_service.get_data(force_refresh=True)
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
        success = japan_terms_of_trade_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
