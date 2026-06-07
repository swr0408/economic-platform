"""
Japan GDP Gap API Router
GDPギャップ APIエンドポイント
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.japan_gdp_gap_service import japan_gdp_gap_service
except ImportError:
    from services.japan.japan_gdp_gap_service import japan_gdp_gap_service

router = APIRouter(prefix="/api/japan/gdp-gap", tags=["Japan Economy"])


@router.get("")
def get_gdp_gap_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    GDPギャップデータを取得

    - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
    """
    return japan_gdp_gap_service.get_data(force_refresh=force_refresh)


@router.get("/cache/status")
def get_cache_status():
    """キャッシュステータスを取得"""
    return japan_gdp_gap_service.get_cache_status()


@router.post("/cache/refresh")
def refresh_cache():
    """キャッシュを強制更新"""
    result = japan_gdp_gap_service.get_data(force_refresh=True)
    return {
        "success": True,
        "message": "Cache refreshed",
        "data_count": len(result.get("data", [])),
        "latest": result.get("latest"),
    }


@router.delete("/cache")
def invalidate_cache():
    """キャッシュを無効化"""
    success = japan_gdp_gap_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
