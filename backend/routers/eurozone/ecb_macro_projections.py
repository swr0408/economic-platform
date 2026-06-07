"""
ECBマクロ経済予測APIルーター

エンドポイント:
- GET /api/eurozone/ecb-macro-projections - ECBマクロ経済予測データを取得
- GET /api/eurozone/ecb-macro-projections/cache/status - キャッシュ状態を取得
- POST /api/eurozone/ecb-macro-projections/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_macro_projections_service import ecb_macro_projections_service
except ImportError:
    from services.eurozone.ecb_macro_projections_service import ecb_macro_projections_service


router = APIRouter(
    prefix="/api/eurozone/ecb-macro-projections",
    tags=["eurozone", "ecb-macro-projections"]
)


@router.get("")
def get_ecb_macro_projections(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ECBマクロ経済予測データを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        ECBマクロ経済予測データ（新API構造）
        - indicators: 各指標のデータ（annual_latest, annual_previous, quarterly_latest, quarterly_previous）
        - metadata: ヴィンテージ情報など
    """
    result = ecb_macro_projections_service.get_ecb_macro_projections_data(force_refresh=refresh)

    if not result.get("indicators") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "indicators": result.get("indicators", {}),
        "metadata": result.get("metadata", {}),
    }


@router.get("/cache/status")
def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_macro_projections_service.get_cache_status()


@router.post("/cache/invalidate")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = ecb_macro_projections_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
