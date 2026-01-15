"""
ECB HICP (Harmonised Index of Consumer Prices) ルーター
ユーロ圏消費者物価調和指数エンドポイント
"""
from fastapi import APIRouter, Query

from services.eurozone.ecb_hicp_service import ecb_hicp_service

router = APIRouter(
    prefix="/ecb-hicp",
    tags=["eurozone", "inflation"]
)


@router.get("")
async def get_ecb_hicp(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    ECB HICP データを取得

    Returns:
        ECB HICP データ（前年比、前月比、内訳）
    """
    return ecb_hicp_service.get_ecb_hicp_data(force_refresh=force_refresh)


@router.post("/refresh")
async def refresh_ecb_hicp():
    """
    ECB HICP データを強制更新

    Returns:
        更新されたECB HICP データ
    """
    return ecb_hicp_service.get_ecb_hicp_data(force_refresh=True)


@router.get("/cache-status")
async def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_hicp_service.get_cache_status()


@router.delete("/cache")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = ecb_hicp_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
