"""
Eurostat Wages API Router
ユーロ圏賃金・給与 APIエンドポイント
"""
from fastapi import APIRouter, Query

try:
    from backend.services.eurozone.eurostat_wages_service import eurostat_wages_service
except ImportError:
    from services.eurozone.eurostat_wages_service import eurostat_wages_service

router = APIRouter(prefix="/api/eurozone/wages", tags=["Eurozone Employment"])


@router.get("")
async def get_eurostat_wages_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    ユーロ圏賃金・給与データを取得

    - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
    """
    return eurostat_wages_service.get_data(force_refresh=force_refresh)


@router.get("/cache/status")
async def get_cache_status():
    """キャッシュステータスを取得"""
    return eurostat_wages_service.get_cache_status()


@router.post("/cache/refresh")
async def refresh_cache():
    """キャッシュを強制更新"""
    result = eurostat_wages_service.get_data(force_refresh=True)
    return {
        "success": True,
        "message": "Cache refreshed",
        "data_count": len(result.get("data", [])),
        "latest": result.get("latest"),
    }


@router.delete("/cache")
async def invalidate_cache():
    """キャッシュを無効化"""
    success = eurostat_wages_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
