"""
企業の物価見通し（BOJ Tankan 表7）API Router

全規模合計・全産業・1年後の「販売価格の見通し」「物価全般の見通し」を四半期時系列で提供。

エンドポイント:
- GET    /api/japan/inflation-outlook              - データ取得
- GET    /api/japan/inflation-outlook/cache-status - キャッシュステータス
- POST   /api/japan/inflation-outlook/refresh      - 強制更新
- DELETE /api/japan/inflation-outlook/cache        - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.boj_inflation_outlook_service import boj_inflation_outlook_service
except ImportError:
    from services.japan.boj_inflation_outlook_service import boj_inflation_outlook_service

router = APIRouter(prefix="/api/japan/inflation-outlook", tags=["Japan - Inflation Outlook"])


@router.get("")
def get_inflation_outlook_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """企業の物価見通しデータ（四半期）を取得"""
    try:
        return boj_inflation_outlook_service.get_data(force_refresh=force_refresh)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-status")
def get_cache_status():
    """キャッシュステータスを取得"""
    try:
        return boj_inflation_outlook_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def refresh_data():
    """データを強制更新"""
    try:
        result = boj_inflation_outlook_service.get_data(force_refresh=True)
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
        success = boj_inflation_outlook_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
