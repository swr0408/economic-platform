"""
Japan POS-UVPI API Router
消費者購買単価指数（POS-UVPI）APIエンドポイント
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.japan_pos_uvpi_service import japan_pos_uvpi_service
except ImportError:
    from services.japan.japan_pos_uvpi_service import japan_pos_uvpi_service

router = APIRouter(prefix="/api/japan/pos-uvpi", tags=["Japan Price"])


@router.get("")
def get_pos_uvpi_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    POS-UVPI（消費者購買単価指数）データを取得

    - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
    """
    return japan_pos_uvpi_service.get_data(force_refresh=force_refresh)


@router.get("/cache/status")
def get_cache_status():
    """キャッシュステータスを取得"""
    return japan_pos_uvpi_service.get_cache_status()


@router.post("/cache/refresh")
def refresh_cache():
    """キャッシュを強制更新"""
    result = japan_pos_uvpi_service.get_data(force_refresh=True)
    return {
        "success": True,
        "message": "Cache refreshed",
        "data_count": len(result.get("data", [])),
        "latest": result.get("latest"),
    }


@router.delete("/cache")
def invalidate_cache():
    """キャッシュを無効化"""
    success = japan_pos_uvpi_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
