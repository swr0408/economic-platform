"""
Japan Industrial Production Index (IIP) Router
API endpoints for Japan IIP data (鉱工業生産指数)

Endpoints:
- GET /api/japan/iip - IIPデータ取得（前月比含む）
- GET /api/japan/iip-yoy - IIP YoYデータ取得
- GET /api/japan/iip/cache-status - キャッシュステータス
- POST /api/japan/iip/refresh - データ強制更新
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.japan_iip_service import japan_iip_service
    from backend.services.japan.japan_iip_yoy_service import japan_iip_yoy_service
except ImportError:
    from services.japan.japan_iip_service import japan_iip_service
    from services.japan.japan_iip_yoy_service import japan_iip_yoy_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Industrial Production"])


@router.get("/iip")
async def get_iip_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    鉱工業生産指数データを取得（前月比含む）

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        鉱工業生産指数データ（月次、前月比 %）
    """
    try:
        result = japan_iip_service.get_iip_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iip-yoy")
async def get_iip_yoy_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    鉱工業生産指数データを取得（前年比）

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        鉱工業生産指数データ（月次、前年比 %）
    """
    try:
        result = japan_iip_yoy_service.get_iip_yoy_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iip/cache-status")
async def get_iip_cache_status():
    """
    キャッシュステータスを取得（MoM）
    """
    try:
        return japan_iip_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iip-yoy/cache-status")
async def get_iip_yoy_cache_status():
    """
    キャッシュステータスを取得（YoY）
    """
    try:
        return japan_iip_yoy_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/iip/refresh")
async def refresh_iip_data():
    """
    IIPデータを強制更新（MoM）
    """
    try:
        result = japan_iip_service.get_iip_data(force_refresh=True)
        return {
            "status": "refreshed",
            "data_count": len(result.get("data", [])),
            "latest": result.get("latest"),
            "last_updated": result.get("last_updated")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/iip-yoy/refresh")
async def refresh_iip_yoy_data():
    """
    IIPデータを強制更新（YoY）
    """
    try:
        result = japan_iip_yoy_service.get_iip_yoy_data(force_refresh=True)
        return {
            "status": "refreshed",
            "data_count": len(result.get("data", [])),
            "latest": result.get("latest"),
            "last_updated": result.get("last_updated")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/iip/cache")
async def invalidate_iip_cache():
    """
    キャッシュを削除（MoM）
    """
    try:
        success = japan_iip_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/iip-yoy/cache")
async def invalidate_iip_yoy_cache():
    """
    キャッシュを削除（YoY）
    """
    try:
        success = japan_iip_yoy_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
