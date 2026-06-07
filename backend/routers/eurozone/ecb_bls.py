"""
ECB BLS (Bank Lending Survey) APIルーター

エンドポイント:
- GET /api/eurozone/ecb-bls - ECB BLSデータを取得
- GET /api/eurozone/ecb-bls/cache/status - キャッシュ状態を取得
- POST /api/eurozone/ecb-bls/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_bls_service import ecb_bls_service
except ImportError:
    from services.eurozone.ecb_bls_service import ecb_bls_service


router = APIRouter(
    prefix="/api/eurozone/ecb-bls",
    tags=["eurozone", "ecb-bls"]
)


@router.get("")
def get_ecb_bls(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ECB BLSデータを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        ECB BLSデータ（企業向け・家計向け融資の信用基準）
    """
    result = ecb_bls_service.get_ecb_bls_data(force_refresh=refresh)

    if not result.get("enterprises") and not result.get("households") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "enterprises": result.get("enterprises", []),
        "households": result.get("households", []),
        "metadata": result.get("metadata", {}),
    }


@router.get("/cache/status")
def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_bls_service.get_cache_status()


@router.post("/cache/invalidate")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = ecb_bls_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
