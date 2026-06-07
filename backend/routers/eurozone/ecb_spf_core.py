"""
ECB SPF Core (Survey of Professional Forecasters) ルーター
コアインフレ期待エンドポイント
"""
from fastapi import APIRouter, Query

from services.eurozone.ecb_spf_core_service import ecb_spf_core_service

router = APIRouter(
    prefix="/ecb-spf-core",
    tags=["eurozone", "inflation"]
)


@router.get("")
def get_ecb_spf_core(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    ECB SPF Core データを取得

    Returns:
        ECB SPF Core データ（コアインフレ期待: 12ヶ月先、24ヶ月先、長期）
    """
    return ecb_spf_core_service.get_ecb_spf_core_data(force_refresh=force_refresh)


@router.post("/refresh")
def refresh_ecb_spf_core():
    """
    ECB SPF Core データを強制更新

    Returns:
        更新されたECB SPF Core データ
    """
    return ecb_spf_core_service.get_ecb_spf_core_data(force_refresh=True)


@router.get("/cache-status")
def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_spf_core_service.get_cache_status()


@router.delete("/cache")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = ecb_spf_core_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
