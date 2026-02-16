"""
UK経常収支ルーター
ONS Current Accountデータエンドポイント
"""
from fastapi import APIRouter, Query

from services.uk.uk_current_account_service import uk_current_account_service

router = APIRouter(
    prefix="/api/uk",
    tags=["uk", "economy"]
)


@router.get("/uk-current-account")
async def get_uk_current_account(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    UK経常収支データを取得

    Returns:
        経常収支データ（四半期、£ billions）
    """
    return uk_current_account_service.get_data(force_refresh=force_refresh)


@router.post("/uk-current-account/refresh")
async def refresh_uk_current_account():
    """
    UK経常収支データを強制更新

    Returns:
        更新されたUK経常収支データ
    """
    return uk_current_account_service.get_data(force_refresh=True)


@router.get("/uk-current-account/cache-status")
async def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return uk_current_account_service.get_cache_status()


@router.delete("/uk-current-account/cache")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = uk_current_account_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
