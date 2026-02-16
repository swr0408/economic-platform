"""
UK貿易収支ルーター
ONS Trade Balanceデータエンドポイント
"""
from fastapi import APIRouter, Query

from services.uk.uk_trade_balance_service import uk_trade_balance_service

router = APIRouter(
    prefix="/api/uk",
    tags=["uk", "economy"]
)


@router.get("/uk-trade-balance")
async def get_uk_trade_balance(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    UK貿易収支データを取得

    Returns:
        貿易収支データ（月次、£ billions）
    """
    return uk_trade_balance_service.get_data(force_refresh=force_refresh)


@router.post("/uk-trade-balance/refresh")
async def refresh_uk_trade_balance():
    """
    UK貿易収支データを強制更新

    Returns:
        更新されたUK貿易収支データ
    """
    return uk_trade_balance_service.get_data(force_refresh=True)


@router.get("/uk-trade-balance/cache-status")
async def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return uk_trade_balance_service.get_cache_status()


@router.delete("/uk-trade-balance/cache")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = uk_trade_balance_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
