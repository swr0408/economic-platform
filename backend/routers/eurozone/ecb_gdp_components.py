"""
ECB GDP Components APIルーター

エンドポイント:
- GET /api/eurozone/ecb-gdp-components - ECB GDP構成要素データを取得
- GET /api/eurozone/ecb-gdp-components/cache/status - キャッシュ状態を取得
- POST /api/eurozone/ecb-gdp-components/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_gdp_components_service import ecb_gdp_components_service
except ImportError:
    from services.eurozone.ecb_gdp_components_service import ecb_gdp_components_service


router = APIRouter(
    prefix="/api/eurozone/ecb-gdp-components",
    tags=["eurozone", "ecb-gdp-components"]
)


@router.get("")
def get_ecb_gdp_components(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ECB GDP構成要素データを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        ECB GDP構成要素データ（民間消費、政府消費、総固定資本形成、在庫変動、純輸出）
    """
    result = ecb_gdp_components_service.get_ecb_gdp_components_data(force_refresh=refresh)

    if not result.get("components") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "components": result.get("components", {}),
        "metadata": result.get("metadata", {}),
    }


@router.get("/cache/status")
def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_gdp_components_service.get_cache_status()


@router.post("/cache/invalidate")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = ecb_gdp_components_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
