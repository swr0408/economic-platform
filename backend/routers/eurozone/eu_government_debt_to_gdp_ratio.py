"""
EU政府債務残高対GDP比ルーター
Eurostat gov_10q_ggdebt データエンドポイント
"""
from fastapi import APIRouter, Query

from services.eurozone.eu_government_debt_to_gdp_ratio_service import eu_government_debt_to_gdp_ratio_service

router = APIRouter(
    prefix="/api/eurozone",
    tags=["eurozone", "economy"]
)


@router.get("/eu-government-debt-to-gdp-ratio")
async def get_eu_government_debt_to_gdp_ratio(force_refresh: bool = Query(False, description="強制更新フラグ")):
    """
    EU政府債務残高対GDP比データを取得

    Returns:
        国別の政府債務残高対GDP比データ（四半期、% of GDP）
    """
    return eu_government_debt_to_gdp_ratio_service.get_data(force_refresh=force_refresh)


@router.post("/eu-government-debt-to-gdp-ratio/refresh")
async def refresh_eu_government_debt_to_gdp_ratio():
    """
    EU政府債務残高対GDP比データを強制更新

    Returns:
        更新されたデータ
    """
    return eu_government_debt_to_gdp_ratio_service.get_data(force_refresh=True)


@router.get("/eu-government-debt-to-gdp-ratio/cache-status")
async def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return eu_government_debt_to_gdp_ratio_service.get_cache_status()


@router.delete("/eu-government-debt-to-gdp-ratio/cache")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    result = eu_government_debt_to_gdp_ratio_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
