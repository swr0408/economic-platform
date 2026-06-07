"""
ロイター短観 API Router (Reuters Tankan)

エンドポイント:
- GET /api/japan/reuters-tankan - ロイター短観データ取得（製造業/非製造業）
- GET /api/japan/reuters-tankan/cache-status - キャッシュステータス取得
- POST /api/japan/reuters-tankan/refresh - データ強制更新
- DELETE /api/japan/reuters-tankan/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.reuters_tankan_service import reuters_tankan_service
except ImportError:
    from services.japan.reuters_tankan_service import reuters_tankan_service

router = APIRouter(prefix="/api/japan/reuters-tankan", tags=["Japan - Reuters Tankan"])


@router.get("")
def get_reuters_tankan_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """ロイター短観データを取得（製造業/非製造業）"""
    try:
        return reuters_tankan_service.get_reuters_tankan_data(force_refresh=force_refresh)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-status")
def get_cache_status():
    """キャッシュステータスを取得"""
    try:
        return reuters_tankan_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def refresh_data():
    """データを強制更新"""
    try:
        result = reuters_tankan_service.get_reuters_tankan_data(force_refresh=True)
        mfg_count = len(result.get("manufacturing", {}).get("data", [])) if result.get("manufacturing") else 0
        non_mfg_count = len(result.get("non_manufacturing", {}).get("data", [])) if result.get("non_manufacturing") else 0
        return {
            "status": "refreshed",
            "data_count": {
                "manufacturing": mfg_count,
                "non_manufacturing": non_mfg_count,
            },
            "last_updated": result.get("last_updated"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
def invalidate_cache():
    """キャッシュを削除"""
    try:
        success = reuters_tankan_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
