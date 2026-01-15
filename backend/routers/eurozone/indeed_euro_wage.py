"""
Indeed Euro Wage Tracker API Router
Indeed賃金トラッカー（ユーロ圏）APIエンドポイント
"""
from fastapi import APIRouter, Query

try:
    from backend.services.eurozone.indeed_euro_wage_service import indeed_euro_wage_service
except ImportError:
    from services.eurozone.indeed_euro_wage_service import indeed_euro_wage_service

router = APIRouter(prefix="/api/eurozone/indeed-wage", tags=["Eurozone Employment"])


@router.get("")
async def get_indeed_euro_wage_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    Indeed賃金成長データを取得（ドイツ、フランス、ユーロ圏）

    - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
    """
    return indeed_euro_wage_service.get_data(force_refresh=force_refresh)


@router.get("/cache/status")
async def get_cache_status():
    """キャッシュステータスを取得"""
    return indeed_euro_wage_service.get_cache_status()


@router.post("/cache/refresh")
async def refresh_cache():
    """キャッシュを強制更新"""
    result = indeed_euro_wage_service.get_data(force_refresh=True)
    return {
        "success": True,
        "message": "Cache refreshed",
        "germany_count": len(result.get("germany", [])),
        "france_count": len(result.get("france", [])),
        "euro_area_count": len(result.get("euro_area", [])),
        "latest": result.get("latest"),
    }


@router.delete("/cache")
async def invalidate_cache():
    """キャッシュを無効化"""
    success = indeed_euro_wage_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
