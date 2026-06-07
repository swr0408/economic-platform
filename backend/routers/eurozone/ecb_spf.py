"""
ECB SPF (Survey of Professional Forecasters) ルーター
インフレ期待エンドポイント
"""
from fastapi import APIRouter, Query

from services.eurozone.ecb_spf_service import ecb_spf_service

router = APIRouter(
    prefix="/ecb-spf",
    tags=["eurozone", "inflation"]
)


@router.get("")
def get_ecb_spf(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    ECB SPF データを取得

    Returns:
        ECB SPF データ（インフレ期待: 12ヶ月先、24ヶ月先、長期）
    """
    return ecb_spf_service.get_ecb_spf_data(force_refresh=force_refresh)


@router.post("/refresh")
def refresh_ecb_spf():
    """
    ECB SPF データを強制更新

    Returns:
        更新されたECB SPF データ
    """
    return ecb_spf_service.get_ecb_spf_data(force_refresh=True)


@router.get("/cache-status")
def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_spf_service.get_cache_status()


@router.delete("/cache")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = ecb_spf_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
