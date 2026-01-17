"""
BOE Bank Rate (政策金利) ルーター
BOE政策金利エンドポイント
"""
from fastapi import APIRouter, Query

from services.uk.boe_bank_rate_service import boe_bank_rate_service

router = APIRouter(
    prefix="/api/uk",
    tags=["uk", "monetary_policy"]
)


@router.get("/boe-bank-rate")
async def get_boe_bank_rate(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    BOE Bank Rate（政策金利）データを取得

    Returns:
        政策金利データ
    """
    return boe_bank_rate_service.get_boe_bank_rate_data(force_refresh=force_refresh)


@router.post("/boe-bank-rate/refresh")
async def refresh_boe_bank_rate():
    """
    BOE Bank Rateデータを強制更新

    Returns:
        更新された政策金利データ
    """
    return boe_bank_rate_service.get_boe_bank_rate_data(force_refresh=True)


@router.get("/boe-bank-rate/cache-status")
async def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return boe_bank_rate_service.get_cache_status()


@router.delete("/boe-bank-rate/cache")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = boe_bank_rate_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
