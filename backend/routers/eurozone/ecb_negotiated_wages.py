"""
ECB Negotiated Wages API Router
ECB交渉妥結賃金 APIエンドポイント
"""
from fastapi import APIRouter, Query

try:
    from backend.services.eurozone.ecb_negotiated_wages_service import ecb_negotiated_wages_service
except ImportError:
    from services.eurozone.ecb_negotiated_wages_service import ecb_negotiated_wages_service

router = APIRouter(prefix="/api/eurozone/negotiated-wages", tags=["Eurozone Employment"])


@router.get("")
def get_ecb_negotiated_wages_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    ECB交渉妥結賃金データを取得

    - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
    """
    return ecb_negotiated_wages_service.get_data(force_refresh=force_refresh)


@router.get("/cache/status")
def get_cache_status():
    """キャッシュステータスを取得"""
    return ecb_negotiated_wages_service.get_cache_status()


@router.post("/cache/refresh")
def refresh_cache():
    """キャッシュを強制更新"""
    result = ecb_negotiated_wages_service.get_data(force_refresh=True)
    return {
        "success": True,
        "message": "Cache refreshed",
        "data_count": len(result.get("data", [])),
        "latest": result.get("latest"),
    }


@router.delete("/cache")
def invalidate_cache():
    """キャッシュを無効化"""
    success = ecb_negotiated_wages_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
