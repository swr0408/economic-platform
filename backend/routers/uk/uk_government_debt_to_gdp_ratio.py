"""
UK政府債務残高対GDP比ルーター
ONS Public Sector Financeデータエンドポイント
"""
from fastapi import APIRouter, Query

from services.uk.uk_government_debt_to_gdp_ratio_service import uk_government_debt_to_gdp_ratio_service

router = APIRouter(
    prefix="/api/uk",
    tags=["uk", "economy"]
)


@router.get("/uk-government-debt-to-gdp-ratio")
async def get_uk_government_debt_to_gdp_ratio(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    UK政府債務残高対GDP比データを取得

    Returns:
        政府債務残高対GDP比データ（月次、% of GDP）
    """
    return uk_government_debt_to_gdp_ratio_service.get_data(force_refresh=force_refresh)


@router.post("/uk-government-debt-to-gdp-ratio/refresh")
async def refresh_uk_government_debt_to_gdp_ratio():
    """
    UK政府債務残高対GDP比データを強制更新

    Returns:
        更新されたデータ
    """
    return uk_government_debt_to_gdp_ratio_service.get_data(force_refresh=True)


@router.get("/uk-government-debt-to-gdp-ratio/cache-status")
async def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return uk_government_debt_to_gdp_ratio_service.get_cache_status()


@router.delete("/uk-government-debt-to-gdp-ratio/cache")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = uk_government_debt_to_gdp_ratio_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
