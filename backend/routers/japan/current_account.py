"""
経常収支 API Router

エンドポイント:
- GET /api/japan/current-account - 経常収支データ取得（単位: 億円）
- GET /api/japan/current-account/gdp-ratio - 経常収支対GDP比（単位: %）
- GET /api/japan/current-account/cache-status - キャッシュステータス取得
- POST /api/japan/current-account/refresh - データ強制更新
- DELETE /api/japan/current-account/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.japan_current_account_service import japan_current_account_service
    from backend.services.japan.japan_current_account_gdp_ratio_service import japan_current_account_gdp_ratio_service
except ImportError:
    from services.japan.japan_current_account_service import japan_current_account_service
    from services.japan.japan_current_account_gdp_ratio_service import japan_current_account_gdp_ratio_service

router = APIRouter(prefix="/api/japan/current-account", tags=["Japan - Current Account"])


@router.get("")
def get_current_account_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    経常収支データを取得

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        経常収支データ（月次、単位: 億円）
    """
    try:
        result = japan_current_account_service.get_current_account_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gdp-ratio")
def get_current_account_gdp_ratio(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    経常収支対GDP比を取得

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        経常収支対GDP比（四半期、単位: %）
    """
    try:
        result = japan_current_account_gdp_ratio_service.get_current_account_gdp_ratio_data(force_refresh=force_refresh)
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
        return japan_current_account_service.get_cache_status()
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
        result = japan_current_account_service.get_current_account_data(force_refresh=True)
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
        success = japan_current_account_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
