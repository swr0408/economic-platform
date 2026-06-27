"""
Stats NZ関連 APIルーター

エンドポイント:
- GET /api/newzealand/stats-nz/ppi - PPI（生産者物価指数）データ
- GET /api/newzealand/stats-nz/ppi/cache - PPIキャッシュ状態
- DELETE /api/newzealand/stats-nz/ppi/cache - PPIキャッシュ無効化
- GET /api/newzealand/stats-nz/cpi - CPI（消費者物価指数）データ
- GET /api/newzealand/stats-nz/cpi/cache - CPIキャッシュ状態
- DELETE /api/newzealand/stats-nz/cpi/cache - CPIキャッシュ無効化
- GET /api/newzealand/stats-nz/number-of-employees - 雇用者数データ
- GET /api/newzealand/stats-nz/number-of-employees/cache - 雇用者数キャッシュ状態
- DELETE /api/newzealand/stats-nz/number-of-employees/cache - 雇用者数キャッシュ無効化
- GET /api/newzealand/stats-nz/unemployment-rate - 失業率データ
- GET /api/newzealand/stats-nz/unemployment-rate/cache - 失業率キャッシュ状態
- DELETE /api/newzealand/stats-nz/unemployment-rate/cache - 失業率キャッシュ無効化
- GET /api/newzealand/stats-nz/wages - 賃金データ（LCI + QES）
- GET /api/newzealand/stats-nz/wages/cache - 賃金キャッシュ状態
- DELETE /api/newzealand/stats-nz/wages/cache - 賃金キャッシュ無効化
- GET /api/newzealand/stats-nz/labour-force-participation - 労働参加率データ
- GET /api/newzealand/stats-nz/labour-force-participation/cache - 労働参加率キャッシュ状態
- DELETE /api/newzealand/stats-nz/labour-force-participation/cache - 労働参加率キャッシュ無効化
- GET /api/newzealand/stats-nz/labor-cost-index - 労働コスト指数データ
- GET /api/newzealand/stats-nz/labor-cost-index/cache - 労働コスト指数キャッシュ状態
- DELETE /api/newzealand/stats-nz/labor-cost-index/cache - 労働コスト指数キャッシュ無効化
- GET /api/newzealand/stats-nz/retail-sales - 小売売上高データ
- GET /api/newzealand/stats-nz/retail-sales/cache - 小売売上高キャッシュ状態
- DELETE /api/newzealand/stats-nz/retail-sales/cache - 小売売上高キャッシュ無効化
- GET /api/newzealand/stats-nz/gdp-growth-rate - GDP成長率データ
- GET /api/newzealand/stats-nz/gdp-growth-rate/cache - GDP成長率キャッシュ状態
- DELETE /api/newzealand/stats-nz/gdp-growth-rate/cache - GDP成長率キャッシュ無効化
- GET /api/newzealand/stats-nz/gdp-item - GDP項目別データ
- GET /api/newzealand/stats-nz/gdp-item/cache - GDP項目別キャッシュ状態
- DELETE /api/newzealand/stats-nz/gdp-item/cache - GDP項目別キャッシュ無効化
- GET /api/newzealand/stats-nz/terms-of-trade - 交易条件データ
- GET /api/newzealand/stats-nz/terms-of-trade/cache - 交易条件キャッシュ状態
- DELETE /api/newzealand/stats-nz/terms-of-trade/cache - 交易条件キャッシュ無効化
- GET /api/newzealand/stats-nz/trade-balance - 貿易収支データ
- GET /api/newzealand/stats-nz/trade-balance/cache - 貿易収支キャッシュ状態
- DELETE /api/newzealand/stats-nz/trade-balance/cache - 貿易収支キャッシュ無効化
- GET /api/newzealand/stats-nz/current-account-balance - 経常収支データ
- GET /api/newzealand/stats-nz/current-account-balance/cache - 経常収支キャッシュ状態
- DELETE /api/newzealand/stats-nz/current-account-balance/cache - 経常収支キャッシュ無効化
- GET /api/newzealand/stats-nz/current-account-gdp-ratio - 経常収支対GDP比データ
- GET /api/newzealand/stats-nz/current-account-gdp-ratio/cache - 経常収支対GDP比キャッシュ状態
- DELETE /api/newzealand/stats-nz/current-account-gdp-ratio/cache - 経常収支対GDP比キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.newzealand.nz_ppi_service import nz_ppi_service
from services.newzealand.nz_cpi_service import nz_cpi_service
from services.newzealand.nz_cpi_item_service import nz_cpi_item_service
from services.newzealand.nz_number_of_employees_service import nz_number_of_employees_service
from services.newzealand.nz_unemployment_rate_service import nz_unemployment_rate_service
from services.newzealand.nz_wages_service import nz_wages_service
from services.newzealand.nz_labour_force_participation_service import nz_labour_force_participation_service
from services.newzealand.nz_labor_cost_index_service import nz_labor_cost_index_service
from services.newzealand.nz_retail_sales_service import nz_retail_sales_service
from services.newzealand.nz_gdp_growth_rate_service import nz_gdp_growth_rate_service
from services.newzealand.nz_gdp_item_service import nz_gdp_item_service
from services.newzealand.nz_terms_of_trade_service import nz_terms_of_trade_service
from services.newzealand.nz_trade_balance_service import nz_trade_balance_service
from services.newzealand.nz_current_account_balance_service import nz_current_account_balance_service
from services.newzealand.nz_current_account_gdp_ratio_service import nz_current_account_gdp_ratio_service

router = APIRouter(
    prefix="/api/newzealand/stats-nz",
    tags=["newzealand", "inflation"]
)


@router.get("/ppi")
def get_ppi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    NZ生産者物価指数（PPI）データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return nz_ppi_service.get_nz_ppi_data(force_refresh=force_refresh)


@router.get("/ppi/cache")
def get_ppi_cache_status() -> Dict[str, Any]:
    """PPIのキャッシュ状態を取得"""
    return nz_ppi_service.get_cache_status()


@router.delete("/ppi/cache")
def invalidate_ppi_cache() -> Dict[str, bool]:
    """PPIのキャッシュを無効化"""
    success = nz_ppi_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# CPI（消費者物価指数）
# =============================================================================

@router.get("/cpi")
def get_cpi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ消費者物価指数（CPI）データを取得"""
    return nz_cpi_service.get_nz_cpi_data(force_refresh=force_refresh)


@router.get("/cpi/cache")
def get_cpi_cache_status() -> Dict[str, Any]:
    """CPIのキャッシュ状態を取得"""
    return nz_cpi_service.get_cache_status()


@router.delete("/cpi/cache")
def invalidate_cpi_cache() -> Dict[str, bool]:
    """CPIのキャッシュを無効化"""
    success = nz_cpi_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# CPI項目別
# =============================================================================

@router.get("/cpi-item")
def get_cpi_item(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ CPI項目別データを取得"""
    return nz_cpi_item_service.get_nz_cpi_item_data(force_refresh=force_refresh)


@router.get("/cpi-item/cache")
def get_cpi_item_cache_status() -> Dict[str, Any]:
    """CPI項目別のキャッシュ状態を取得"""
    return nz_cpi_item_service.get_cache_status()


@router.delete("/cpi-item/cache")
def invalidate_cpi_item_cache() -> Dict[str, bool]:
    """CPI項目別のキャッシュを無効化"""
    success = nz_cpi_item_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 雇用者数（HLFS）
# =============================================================================

@router.get("/number-of-employees")
def get_number_of_employees(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 雇用者数（総雇用者数・フルタイム・パートタイム）データを取得"""
    return nz_number_of_employees_service.get_data(force_refresh=force_refresh)


@router.get("/number-of-employees/cache")
def get_number_of_employees_cache_status() -> Dict[str, Any]:
    """雇用者数のキャッシュ状態を取得"""
    return nz_number_of_employees_service.get_cache_status()


@router.delete("/number-of-employees/cache")
def invalidate_number_of_employees_cache() -> Dict[str, bool]:
    """雇用者数のキャッシュを無効化"""
    success = nz_number_of_employees_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 失業率（HLFS）
# =============================================================================

@router.get("/unemployment-rate")
def get_unemployment_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 失業率（季節調整済み）データを取得"""
    return nz_unemployment_rate_service.get_data(force_refresh=force_refresh)


@router.get("/unemployment-rate/cache")
def get_unemployment_rate_cache_status() -> Dict[str, Any]:
    """失業率のキャッシュ状態を取得"""
    return nz_unemployment_rate_service.get_cache_status()


@router.delete("/unemployment-rate/cache")
def invalidate_unemployment_rate_cache() -> Dict[str, bool]:
    """失業率のキャッシュを無効化"""
    success = nz_unemployment_rate_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 賃金（LCI + QES）
# =============================================================================

@router.get("/wages")
def get_wages(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 賃金データ（全給与・賃金率指数 + 平均時給）を取得"""
    return nz_wages_service.get_data(force_refresh=force_refresh)


@router.get("/wages/cache")
def get_wages_cache_status() -> Dict[str, Any]:
    """賃金のキャッシュ状態を取得"""
    return nz_wages_service.get_cache_status()


@router.delete("/wages/cache")
def invalidate_wages_cache() -> Dict[str, bool]:
    """賃金のキャッシュを無効化"""
    success = nz_wages_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 労働参加率（HLFS）
# =============================================================================

@router.get("/labour-force-participation")
def get_labour_force_participation(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 労働参加率（季節調整済み）データを取得"""
    return nz_labour_force_participation_service.get_data(force_refresh=force_refresh)


@router.get("/labour-force-participation/cache")
def get_labour_force_participation_cache_status() -> Dict[str, Any]:
    """労働参加率のキャッシュ状態を取得"""
    return nz_labour_force_participation_service.get_cache_status()


@router.delete("/labour-force-participation/cache")
def invalidate_labour_force_participation_cache() -> Dict[str, bool]:
    """労働参加率のキャッシュを無効化"""
    success = nz_labour_force_participation_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 労働コスト指数（LCI）
# =============================================================================

@router.get("/labor-cost-index")
def get_labor_cost_index(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 労働コスト指数データを取得"""
    return nz_labor_cost_index_service.get_data(force_refresh=force_refresh)


@router.get("/labor-cost-index/cache")
def get_labor_cost_index_cache_status() -> Dict[str, Any]:
    """労働コスト指数のキャッシュ状態を取得"""
    return nz_labor_cost_index_service.get_cache_status()


@router.delete("/labor-cost-index/cache")
def invalidate_labor_cost_index_cache() -> Dict[str, bool]:
    """労働コスト指数のキャッシュを無効化"""
    success = nz_labor_cost_index_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 小売売上高（Retail Trade Survey）
# =============================================================================

@router.get("/retail-sales")
def get_retail_sales(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 小売売上高データを取得"""
    return nz_retail_sales_service.get_data(force_refresh=force_refresh)


@router.get("/retail-sales/cache")
def get_retail_sales_cache_status() -> Dict[str, Any]:
    """小売売上高のキャッシュ状態を取得"""
    return nz_retail_sales_service.get_cache_status()


@router.delete("/retail-sales/cache")
def invalidate_retail_sales_cache() -> Dict[str, bool]:
    """小売売上高のキャッシュを無効化"""
    success = nz_retail_sales_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# GDP成長率
# =============================================================================

@router.get("/gdp-growth-rate")
def get_gdp_growth_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ GDP成長率データを取得"""
    return nz_gdp_growth_rate_service.get_data(force_refresh=force_refresh)


@router.get("/gdp-growth-rate/cache")
def get_gdp_growth_rate_cache_status() -> Dict[str, Any]:
    """GDP成長率のキャッシュ状態を取得"""
    return nz_gdp_growth_rate_service.get_cache_status()


@router.delete("/gdp-growth-rate/cache")
def invalidate_gdp_growth_rate_cache() -> Dict[str, bool]:
    """GDP成長率のキャッシュを無効化"""
    success = nz_gdp_growth_rate_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# GDP項目別
# =============================================================================

@router.get("/gdp-item")
def get_gdp_item(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ GDP項目別データを取得"""
    return nz_gdp_item_service.get_data(force_refresh=force_refresh)


@router.get("/gdp-item/cache")
def get_gdp_item_cache_status() -> Dict[str, Any]:
    """GDP項目別のキャッシュ状態を取得"""
    return nz_gdp_item_service.get_cache_status()


@router.delete("/gdp-item/cache")
def invalidate_gdp_item_cache() -> Dict[str, bool]:
    """GDP項目別のキャッシュを無効化"""
    success = nz_gdp_item_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 交易条件（Terms of Trade）
# =============================================================================

@router.get("/terms-of-trade")
def get_terms_of_trade(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 交易条件データを取得"""
    return nz_terms_of_trade_service.get_data(force_refresh=force_refresh)


@router.get("/terms-of-trade/cache")
def get_terms_of_trade_cache_status() -> Dict[str, Any]:
    """交易条件のキャッシュ状態を取得"""
    return nz_terms_of_trade_service.get_cache_status()


@router.delete("/terms-of-trade/cache")
def invalidate_terms_of_trade_cache() -> Dict[str, bool]:
    """交易条件のキャッシュを無効化"""
    success = nz_terms_of_trade_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 貿易収支（Trade Balance）
# =============================================================================

@router.get("/trade-balance")
def get_trade_balance(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 貿易収支データを取得"""
    return nz_trade_balance_service.get_data(force_refresh=force_refresh)


@router.get("/trade-balance/cache")
def get_trade_balance_cache_status() -> Dict[str, Any]:
    """貿易収支のキャッシュ状態を取得"""
    cached = nz_trade_balance_service._load_file_cache()
    return {
        "has_cache": cached is not None,
        "last_updated": cached.get("last_updated") if cached else None,
        "record_count": len(cached.get("data", [])) if cached else 0,
    }


@router.delete("/trade-balance/cache")
def invalidate_trade_balance_cache() -> Dict[str, bool]:
    """貿易収支のキャッシュを無効化"""
    from core.redis_client import redis_client
    success = redis_client.delete(nz_trade_balance_service.DATA_CACHE_KEY)
    return {"success": bool(success)}


# =============================================================================
# 経常収支（Current Account Balance）
# =============================================================================

@router.get("/current-account-balance")
def get_current_account_balance(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 経常収支データを取得"""
    return nz_current_account_balance_service.get_data(force_refresh=force_refresh)


@router.get("/current-account-balance/cache")
def get_current_account_balance_cache_status() -> Dict[str, Any]:
    """経常収支のキャッシュ状態を取得"""
    return nz_current_account_balance_service.get_cache_status()


@router.delete("/current-account-balance/cache")
def invalidate_current_account_balance_cache() -> Dict[str, bool]:
    """経常収支のキャッシュを無効化"""
    success = nz_current_account_balance_service.invalidate_cache()
    return {"success": bool(success)}


# =============================================================================
# 経常収支対GDP比（Current Account / GDP Ratio）
# =============================================================================

@router.get("/current-account-gdp-ratio")
def get_current_account_gdp_ratio(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 経常収支対GDP比データを取得"""
    return nz_current_account_gdp_ratio_service.get_data(force_refresh=force_refresh)


@router.get("/current-account-gdp-ratio/cache")
def get_current_account_gdp_ratio_cache_status() -> Dict[str, Any]:
    """経常収支対GDP比のキャッシュ状態を取得"""
    return nz_current_account_gdp_ratio_service.get_cache_status()


@router.delete("/current-account-gdp-ratio/cache")
def invalidate_current_account_gdp_ratio_cache() -> Dict[str, bool]:
    """経常収支対GDP比のキャッシュを無効化"""
    success = nz_current_account_gdp_ratio_service.invalidate_cache()
    return {"success": bool(success)}
