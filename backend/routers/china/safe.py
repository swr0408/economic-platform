"""
中国 国家外貨管理局（SAFE）関連 APIルーター

エンドポイント:
- GET /api/china/safe/current-account - 経常収支データ
- GET /api/china/safe/current-account/cache - キャッシュ状態
- DELETE /api/china/safe/current-account/cache - キャッシュ無効化
- GET /api/china/safe/current-account-gdp-ratio - 経常収支対GDP比データ
- GET /api/china/safe/current-account-gdp-ratio/cache - キャッシュ状態
- DELETE /api/china/safe/current-account-gdp-ratio/cache - キャッシュ無効化
- GET /api/china/safe/capital-flows - 資本フローデータ
- GET /api/china/safe/capital-flows/cache - キャッシュ状態
- DELETE /api/china/safe/capital-flows/cache - キャッシュ無効化
- GET /api/china/safe/gold-reserves - 金準備データ
- GET /api/china/safe/gold-reserves/cache - キャッシュ状態
- DELETE /api/china/safe/gold-reserves/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.china.cn_current_account_service import cn_current_account_service
from services.china.cn_current_account_gdp_ratio_service import cn_current_account_gdp_ratio_service
from services.china.cn_capital_flows_service import cn_capital_flows_service
from services.china.cn_gold_reserves_service import cn_gold_reserves_service

router = APIRouter(
    prefix="/api/china/safe",
    tags=["china", "safe"]
)


# -------------------------------------------------------------------------
# 経常収支（Current Account）
# -------------------------------------------------------------------------

@router.get("/current-account")
async def get_current_account(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """経常収支（四半期、億USD）データを返す"""
    return cn_current_account_service.get_data(force_refresh=force_refresh)


@router.get("/current-account/cache")
async def get_current_account_cache_status() -> Dict[str, Any]:
    """経常収支のキャッシュ状態を返す"""
    return cn_current_account_service.get_cache_status()


@router.delete("/current-account/cache")
async def invalidate_current_account_cache() -> Dict[str, Any]:
    """経常収支のキャッシュを無効化"""
    return cn_current_account_service.invalidate_cache()


# -------------------------------------------------------------------------
# 経常収支対GDP比（Current Account to GDP Ratio）
# -------------------------------------------------------------------------

@router.get("/current-account-gdp-ratio")
async def get_current_account_gdp_ratio(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """経常収支対GDP比（四半期、%）データを返す"""
    return cn_current_account_gdp_ratio_service.get_data(force_refresh=force_refresh)


@router.get("/current-account-gdp-ratio/cache")
async def get_current_account_gdp_ratio_cache_status() -> Dict[str, Any]:
    """経常収支対GDP比のキャッシュ状態を返す"""
    return cn_current_account_gdp_ratio_service.get_cache_status()


@router.delete("/current-account-gdp-ratio/cache")
async def invalidate_current_account_gdp_ratio_cache() -> Dict[str, Any]:
    """経常収支対GDP比のキャッシュを無効化"""
    return cn_current_account_gdp_ratio_service.invalidate_cache()


# -------------------------------------------------------------------------
# 資本フロー（Capital Flows）
# -------------------------------------------------------------------------

@router.get("/capital-flows")
async def get_capital_flows(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """資本フロー（月次、億USD）データを返す"""
    return cn_capital_flows_service.get_data(force_refresh=force_refresh)


@router.get("/capital-flows/cache")
async def get_capital_flows_cache_status() -> Dict[str, Any]:
    """資本フローのキャッシュ状態を返す"""
    return cn_capital_flows_service.get_cache_status()


@router.delete("/capital-flows/cache")
async def invalidate_capital_flows_cache() -> Dict[str, Any]:
    """資本フローのキャッシュを無効化"""
    return cn_capital_flows_service.invalidate_cache()


# -------------------------------------------------------------------------
# 金準備（Gold Reserves）
# -------------------------------------------------------------------------

@router.get("/gold-reserves")
def get_gold_reserves(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """金準備（月次、万トロイオンス / 億USD）データを返す"""
    return cn_gold_reserves_service.get_data(force_refresh=force_refresh)


@router.get("/gold-reserves/cache")
def get_gold_reserves_cache_status() -> Dict[str, Any]:
    """金準備のキャッシュ状態を返す"""
    return cn_gold_reserves_service.get_cache_status()


@router.delete("/gold-reserves/cache")
def invalidate_gold_reserves_cache() -> Dict[str, Any]:
    """金準備のキャッシュを無効化"""
    return cn_gold_reserves_service.invalidate_cache()
