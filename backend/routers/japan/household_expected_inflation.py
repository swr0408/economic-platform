"""
日銀 家計予想物価上昇率 API Router
生活意識に関するアンケート調査（家計の物価予想・実感）APIエンドポイント
"""
from fastapi import APIRouter, Query

try:
    from backend.services.japan.household_expected_inflation_service import household_expected_inflation_service
except ImportError:
    from services.japan.household_expected_inflation_service import household_expected_inflation_service

router = APIRouter(prefix="/api/japan/household-expected-inflation", tags=["Japan Price"])


@router.get("")
def get_household_expected_inflation_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    日銀 家計予想物価上昇率データを取得

    - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
    """
    return household_expected_inflation_service.get_data(force_refresh=force_refresh)


@router.get("/cache/status")
def get_cache_status():
    """キャッシュステータスを取得"""
    return household_expected_inflation_service.get_cache_status()


@router.post("/cache/refresh")
def refresh_cache():
    """キャッシュを強制更新"""
    result = household_expected_inflation_service.get_data(force_refresh=True)
    return {
        "success": True,
        "message": "Cache refreshed",
        "data_count": len(result.get("data", [])),
        "latest": result.get("latest"),
    }


@router.delete("/cache")
def invalidate_cache():
    """キャッシュを無効化"""
    success = household_expected_inflation_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Failed to invalidate cache"}
