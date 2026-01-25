"""
Japan Tertiary Industry Activity Index Router
API endpoints for Japan Tertiary Industry Index data (第三次産業活動指数)

Endpoints:
- GET /api/japan/tertiary-industry-index - 第三次産業活動指数データ取得
- GET /api/japan/tertiary-industry-index/cache-status - キャッシュステータス
- POST /api/japan/tertiary-industry-index/refresh - データ強制更新
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.tertiary_industry_index_service import tertiary_industry_index_service
except ImportError:
    from services.japan.tertiary_industry_index_service import tertiary_industry_index_service

router = APIRouter(prefix="/api/japan", tags=["Japan - Tertiary Industry"])


@router.get("/tertiary-industry-index")
async def get_tertiary_industry_index_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    第三次産業活動指数データを取得（前月比・前年比）

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        第三次産業活動指数データ（月次、前月比・前年比 %）
    """
    try:
        result = tertiary_industry_index_service.get_tertiary_industry_index_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tertiary-industry-index/cache-status")
async def get_tertiary_industry_index_cache_status():
    """
    キャッシュステータスを取得
    """
    try:
        return tertiary_industry_index_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tertiary-industry-index/refresh")
async def refresh_tertiary_industry_index_data():
    """
    第三次産業活動指数データを強制更新
    """
    try:
        result = tertiary_industry_index_service.get_tertiary_industry_index_data(force_refresh=True)
        return {
            "status": "refreshed",
            "data_count": len(result.get("data", [])),
            "latest": result.get("latest"),
            "last_updated": result.get("last_updated")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tertiary-industry-index/cache")
async def invalidate_tertiary_industry_index_cache():
    """
    キャッシュを削除
    """
    try:
        success = tertiary_industry_index_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
