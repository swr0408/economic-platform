"""
ECB Consumer Expectations Survey (CES) - インフレ期待ルーター
消費者インフレ期待エンドポイント
"""
from fastapi import APIRouter, Query

from services.eurozone.ecb_inflation_expectations_service import ecb_inflation_expectations_service

router = APIRouter(
    prefix="/api/eurozone",
    tags=["eurozone", "inflation"]
)


@router.get("/ecb-inflation-expectations")
async def get_inflation_expectations(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    ECB Consumer Expectations Survey - インフレ期待データを取得

    Returns:
        インフレ期待データ（12ヶ月先、3年先、インフレ認識）
    """
    return ecb_inflation_expectations_service.get_inflation_expectations_data(force_refresh=force_refresh)


@router.post("/ecb-inflation-expectations/refresh")
async def refresh_inflation_expectations():
    """
    インフレ期待データを強制更新

    Returns:
        更新されたインフレ期待データ
    """
    return ecb_inflation_expectations_service.get_inflation_expectations_data(force_refresh=True)


@router.get("/ecb-inflation-expectations/cache-status")
async def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_inflation_expectations_service.get_cache_status()


@router.delete("/ecb-inflation-expectations/cache")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = ecb_inflation_expectations_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
