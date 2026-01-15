"""
Japan CGPI Food & Agriculture API Router
企業物価指数：飲食料品・農林水産物 APIエンドポイント
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.japan_cgpi_food_agriculture_service import japan_cgpi_food_agriculture_service
except ImportError:
    from services.japan.japan_cgpi_food_agriculture_service import japan_cgpi_food_agriculture_service

router = APIRouter(prefix="/api/japan/cgpi-food-agriculture", tags=["Japan Price"])


@router.get("")
async def get_cgpi_food_agriculture_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    企業物価指数：飲食料品・農林水産物データを取得

    - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
    """
    return japan_cgpi_food_agriculture_service.get_data(force_refresh=force_refresh)


@router.get("/cache/status")
async def get_cache_status():
    """キャッシュステータスを取得"""
    return japan_cgpi_food_agriculture_service.get_cache_status()


@router.post("/cache/refresh")
async def refresh_cache():
    """キャッシュを強制更新"""
    result = japan_cgpi_food_agriculture_service.get_data(force_refresh=True)
    return {
        "success": True,
        "message": "Cache refreshed",
        "data_count": len(result.get("data", [])),
        "latest": result.get("latest"),
    }


@router.delete("/cache")
async def invalidate_cache():
    """キャッシュを無効化"""
    success = japan_cgpi_food_agriculture_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
