"""
Japan Import/Export Price Index API Router
輸入・輸出物価指数 APIエンドポイント
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.japan_import_export_price_service import japan_import_export_price_service
except ImportError:
    from services.japan.japan_import_export_price_service import japan_import_export_price_service

router = APIRouter(prefix="/api/japan/import-export-price", tags=["Japan Price"])


@router.get("")
async def get_import_export_price_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    輸入・輸出物価指数データを取得

    - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
    """
    return japan_import_export_price_service.get_data(force_refresh=force_refresh)


@router.get("/cache/status")
async def get_cache_status():
    """キャッシュステータスを取得"""
    return japan_import_export_price_service.get_cache_status()


@router.post("/cache/refresh")
async def refresh_cache():
    """キャッシュを強制更新"""
    result = japan_import_export_price_service.get_data(force_refresh=True)
    return {
        "success": True,
        "message": "Cache refreshed",
        "data_count": len(result.get("data", [])),
        "latest": result.get("latest"),
    }


@router.delete("/cache")
async def invalidate_cache():
    """キャッシュを無効化"""
    success = japan_import_export_price_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
