"""
ECB PPI (Producer Price Index) ルーター
ユーロ圏生産者物価指数エンドポイント
"""
from fastapi import APIRouter, Query

from services.eurozone.ecb_ppi_service import ecb_ppi_service

router = APIRouter(
    prefix="/ecb-ppi",
    tags=["eurozone", "inflation"]
)


@router.get("")
def get_ecb_ppi(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    ECB PPI データを取得

    Returns:
        ECB PPI データ（前年比、前月比）
    """
    return ecb_ppi_service.get_ecb_ppi_data(force_refresh=force_refresh)


@router.post("/refresh")
def refresh_ecb_ppi():
    """
    ECB PPI データを強制更新

    Returns:
        更新されたECB PPI データ
    """
    return ecb_ppi_service.get_ecb_ppi_data(force_refresh=True)


@router.get("/cache-status")
def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_ppi_service.get_cache_status()


@router.delete("/cache")
def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = ecb_ppi_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
