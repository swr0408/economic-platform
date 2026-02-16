"""
Statistics Canada 関連 APIルーター

エンドポイント:
- GET /api/canada/statcan/cpi - カナダCPIデータ
- GET /api/canada/statcan/cpi/cache - CPIキャッシュ状態
- DELETE /api/canada/statcan/cpi/cache - CPIキャッシュ無効化
- GET /api/canada/statcan/ippi - カナダIPPIデータ
- GET /api/canada/statcan/ippi/cache - IPPIキャッシュ状態
- DELETE /api/canada/statcan/ippi/cache - IPPIキャッシュ無効化
- GET /api/canada/statcan/gdp-growth - カナダGDP成長率データ
- GET /api/canada/statcan/gdp-growth/cache - GDP成長率キャッシュ状態
- DELETE /api/canada/statcan/gdp-growth/cache - GDP成長率キャッシュ無効化
- GET /api/canada/statcan/gdp-monthly - カナダ月次GDPデータ
- GET /api/canada/statcan/gdp-monthly/cache - 月次GDPキャッシュ状態
- DELETE /api/canada/statcan/gdp-monthly/cache - 月次GDPキャッシュ無効化
- GET /api/canada/statcan/employment - カナダ雇用者数データ
- GET /api/canada/statcan/employment/cache - 雇用者数キャッシュ状態
- DELETE /api/canada/statcan/employment/cache - 雇用者数キャッシュ無効化
- GET /api/canada/statcan/unemployment-rate - カナダ失業率データ
- GET /api/canada/statcan/unemployment-rate/cache - 失業率キャッシュ状態
- DELETE /api/canada/statcan/unemployment-rate/cache - 失業率キャッシュ無効化
- GET /api/canada/statcan/labor-force-participation-rate - カナダ労働参加率データ
- GET /api/canada/statcan/labor-force-participation-rate/cache - 労働参加率キャッシュ状態
- DELETE /api/canada/statcan/labor-force-participation-rate/cache - 労働参加率キャッシュ無効化
- GET /api/canada/statcan/average-hourly-wage - カナダ平均時給データ
- GET /api/canada/statcan/average-hourly-wage/cache - 平均時給キャッシュ状態
- DELETE /api/canada/statcan/average-hourly-wage/cache - 平均時給キャッシュ無効化
- GET /api/canada/statcan/retail-sales - カナダ小売売上高データ
- GET /api/canada/statcan/retail-sales/cache - 小売売上高キャッシュ状態
- DELETE /api/canada/statcan/retail-sales/cache - 小売売上高キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.canada.ca_cpi_service import ca_cpi_service
from services.canada.ca_ippi_service import ca_ippi_service
from services.canada.ca_gdp_growth_service import ca_gdp_growth_service
from services.canada.ca_gdp_monthly_service import ca_gdp_monthly_service
from services.canada.ca_employment_service import ca_employment_service
from services.canada.ca_unemployment_rate_service import ca_unemployment_rate_service
from services.canada.ca_labor_force_participation_rate_service import ca_labor_force_participation_rate_service
from services.canada.ca_average_hourly_wage_service import ca_average_hourly_wage_service
from services.canada.ca_weekly_average_salary_service import ca_weekly_average_salary_service
from services.canada.ca_retail_sales_service import ca_retail_sales_service
from services.canada.ca_industrial_production_service import ca_industrial_production_service
from services.canada.ca_trade_balance_service import ca_trade_balance_service
from services.canada.ca_current_account_service import ca_current_account_service
from services.canada.ca_current_account_gdp_ratio_service import ca_current_account_gdp_ratio_service
from services.canada.ca_us_export_dependence_service import ca_us_export_dependence_service
from services.canada.ca_housing_starts_service import ca_housing_starts_service
from services.canada.ca_building_permits_service import ca_building_permits_service
from services.canada.ca_new_housing_price_index_service import ca_new_housing_price_index_service
from services.canada.ca_debt_service_ratio_service import ca_debt_service_ratio_service
from services.canada.ca_cpi_service_rent_service import ca_cpi_service_rent_service
from services.canada.ca_job_vacancy_rate_service import ca_job_vacancy_rate_service
from services.canada.ca_ivey_pmi_service import ca_ivey_pmi_service
from services.canada.ca_sp_pmi_service import ca_sp_pmi_service

router = APIRouter(
    prefix="/api/canada/statcan",
    tags=["canada", "inflation"]
)


# ===== CPI =====

@router.get("/cpi")
async def get_ca_cpi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダCPI（消費者物価指数）データを取得

    データソース: Statistics Canada Tables 18-10-0004-01, 18-10-0006-01, 18-10-0256-02

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "yoy": float, "mom": float, "trim": float, "median": float, "common": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_cpi_service.get_ca_cpi_data(force_refresh=force_refresh)


@router.get("/cpi/cache")
async def get_ca_cpi_cache_status() -> Dict[str, Any]:
    """
    カナダCPIのキャッシュ状態を取得
    """
    return ca_cpi_service.get_cache_status()


@router.delete("/cpi/cache")
async def invalidate_ca_cpi_cache() -> Dict[str, bool]:
    """
    カナダCPIのキャッシュを無効化
    """
    success = ca_cpi_service.invalidate_cache()
    return {"success": success}


# ===== IPPI (Industrial Product Price Index) =====

@router.get("/ippi")
async def get_ca_ippi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダIPPI（工業製品価格指数）データを取得

    データソース: Statistics Canada Table 18-10-0265-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "yoy": float, "mom": float, "index": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_ippi_service.get_ca_ippi_data(force_refresh=force_refresh)


@router.get("/ippi/cache")
async def get_ca_ippi_cache_status() -> Dict[str, Any]:
    """
    カナダIPPIのキャッシュ状態を取得
    """
    return ca_ippi_service.get_cache_status()


@router.delete("/ippi/cache")
async def invalidate_ca_ippi_cache() -> Dict[str, bool]:
    """
    カナダIPPIのキャッシュを無効化
    """
    success = ca_ippi_service.invalidate_cache()
    return {"success": success}


# ===== GDP Growth (GDP成長率) =====

@router.get("/gdp-growth")
async def get_ca_gdp_growth(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダGDP成長率データを取得

    データソース: Statistics Canada Table 36-10-0104-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "qoq": float, "yoy": float, "value": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_gdp_growth_service.get_ca_gdp_growth_data(force_refresh=force_refresh)


@router.get("/gdp-growth/cache")
async def get_ca_gdp_growth_cache_status() -> Dict[str, Any]:
    """
    カナダGDP成長率のキャッシュ状態を取得
    """
    return ca_gdp_growth_service.get_cache_status()


@router.delete("/gdp-growth/cache")
async def invalidate_ca_gdp_growth_cache() -> Dict[str, bool]:
    """
    カナダGDP成長率のキャッシュを無効化
    """
    success = ca_gdp_growth_service.invalidate_cache()
    return {"success": success}


# ===== Monthly GDP (月次GDP) =====

@router.get("/gdp-monthly")
async def get_ca_gdp_monthly(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ月次GDPデータを取得

    データソース: Statistics Canada Table 36-10-0434-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "mom": float, "yoy": float, "value": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_gdp_monthly_service.get_ca_gdp_monthly_data(force_refresh=force_refresh)


@router.get("/gdp-monthly/cache")
async def get_ca_gdp_monthly_cache_status() -> Dict[str, Any]:
    """
    カナダ月次GDPのキャッシュ状態を取得
    """
    return ca_gdp_monthly_service.get_cache_status()


@router.delete("/gdp-monthly/cache")
async def invalidate_ca_gdp_monthly_cache() -> Dict[str, bool]:
    """
    カナダ月次GDPのキャッシュを無効化
    """
    success = ca_gdp_monthly_service.invalidate_cache()
    return {"success": success}


# ===== Employment (雇用者数) =====

@router.get("/employment")
async def get_ca_employment(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ雇用者数データを取得

    データソース: Statistics Canada Table 14-10-0287-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "employment": float, "fulltime": float, "parttime": float, "employment_change": float, ...}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_employment_service.get_ca_employment_data(force_refresh=force_refresh)


@router.get("/employment/cache")
async def get_ca_employment_cache_status() -> Dict[str, Any]:
    """
    カナダ雇用者数のキャッシュ状態を取得
    """
    return ca_employment_service.get_cache_status()


@router.delete("/employment/cache")
async def invalidate_ca_employment_cache() -> Dict[str, bool]:
    """
    カナダ雇用者数のキャッシュを無効化
    """
    success = ca_employment_service.invalidate_cache()
    return {"success": success}


# ===== Unemployment Rate (失業率) =====

@router.get("/unemployment-rate")
async def get_ca_unemployment_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ失業率データを取得

    データソース: Statistics Canada Table 14-10-0287-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_unemployment_rate_service.get_ca_unemployment_rate_data(force_refresh=force_refresh)


@router.get("/unemployment-rate/cache")
async def get_ca_unemployment_rate_cache_status() -> Dict[str, Any]:
    """
    カナダ失業率のキャッシュ状態を取得
    """
    return ca_unemployment_rate_service.get_cache_status()


@router.delete("/unemployment-rate/cache")
async def invalidate_ca_unemployment_rate_cache() -> Dict[str, bool]:
    """
    カナダ失業率のキャッシュを無効化
    """
    success = ca_unemployment_rate_service.invalidate_cache()
    return {"success": success}


# ===== Labor Force Participation Rate (労働参加率) =====

@router.get("/labor-force-participation-rate")
async def get_ca_labor_force_participation_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ労働参加率データを取得

    データソース: Statistics Canada Table 14-10-0287-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_labor_force_participation_rate_service.get_ca_labor_force_participation_rate_data(force_refresh=force_refresh)


@router.get("/labor-force-participation-rate/cache")
async def get_ca_labor_force_participation_rate_cache_status() -> Dict[str, Any]:
    """
    カナダ労働参加率のキャッシュ状態を取得
    """
    return ca_labor_force_participation_rate_service.get_cache_status()


@router.delete("/labor-force-participation-rate/cache")
async def invalidate_ca_labor_force_participation_rate_cache() -> Dict[str, bool]:
    """
    カナダ労働参加率のキャッシュを無効化
    """
    success = ca_labor_force_participation_rate_service.invalidate_cache()
    return {"success": success}


# ===== Average Hourly Wage (平均時給) =====

@router.get("/average-hourly-wage")
async def get_ca_average_hourly_wage(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ平均時給データを取得

    データソース: Statistics Canada Table 14-10-0065-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float, "yoy": float, "mom": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_average_hourly_wage_service.get_ca_average_hourly_wage_data(force_refresh=force_refresh)


@router.get("/average-hourly-wage/cache")
async def get_ca_average_hourly_wage_cache_status() -> Dict[str, Any]:
    """
    カナダ平均時給のキャッシュ状態を取得
    """
    return ca_average_hourly_wage_service.get_cache_status()


@router.delete("/average-hourly-wage/cache")
async def invalidate_ca_average_hourly_wage_cache() -> Dict[str, bool]:
    """
    カナダ平均時給のキャッシュを無効化
    """
    success = ca_average_hourly_wage_service.invalidate_cache()
    return {"success": success}


# ===== Weekly Average Salary (週間平均給与) =====

@router.get("/weekly-average-salary")
async def get_ca_weekly_average_salary(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ週間平均給与データを取得

    データソース: Statistics Canada Table 14-10-0022-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float, "yoy": float, "mom": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_weekly_average_salary_service.get_ca_weekly_average_salary_data(force_refresh=force_refresh)


@router.get("/weekly-average-salary/cache")
async def get_ca_weekly_average_salary_cache_status() -> Dict[str, Any]:
    """
    カナダ週間平均給与のキャッシュ状態を取得
    """
    return ca_weekly_average_salary_service.get_cache_status()


@router.delete("/weekly-average-salary/cache")
async def invalidate_ca_weekly_average_salary_cache() -> Dict[str, bool]:
    """
    カナダ週間平均給与のキャッシュを無効化
    """
    success = ca_weekly_average_salary_service.invalidate_cache()
    return {"success": success}


# ===== Retail Sales (小売売上高) =====

@router.get("/retail-sales")
async def get_ca_retail_sales(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ小売売上高データを取得

    データソース: Statistics Canada Table 20-10-0067-01

    系列:
    - total: 総合
    - ex_auto: 除く自動車
    - ex_auto_gas: 除く自動車+ガソリン

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{
                "date": "YYYY-MM-DD",
                "total_mom": float, "total_yoy": float,
                "ex_auto_mom": float, "ex_auto_yoy": float,
                "ex_auto_gas_mom": float, "ex_auto_gas_yoy": float
            }, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_retail_sales_service.get_ca_retail_sales_data(force_refresh=force_refresh)


@router.get("/retail-sales/cache")
async def get_ca_retail_sales_cache_status() -> Dict[str, Any]:
    """
    カナダ小売売上高のキャッシュ状態を取得
    """
    return ca_retail_sales_service.get_cache_status()


@router.delete("/retail-sales/cache")
async def invalidate_ca_retail_sales_cache() -> Dict[str, bool]:
    """
    カナダ小売売上高のキャッシュを無効化
    """
    success = ca_retail_sales_service.invalidate_cache()
    return {"success": success}


# ===== Industrial Production (鉱工業生産) =====

@router.get("/industrial-production")
async def get_ca_industrial_production(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ鉱工業生産データを取得

    データソース: Statistics Canada Table 36-10-0434-01
    系列: Industrial production [T010] (SAAR, Chained 2017 dollars)

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "mom": float, "yoy": float, "value": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_industrial_production_service.get_ca_industrial_production_data(force_refresh=force_refresh)


@router.get("/industrial-production/cache")
async def get_ca_industrial_production_cache_status() -> Dict[str, Any]:
    """
    カナダ鉱工業生産のキャッシュ状態を取得
    """
    return ca_industrial_production_service.get_cache_status()


@router.delete("/industrial-production/cache")
async def invalidate_ca_industrial_production_cache() -> Dict[str, bool]:
    """
    カナダ鉱工業生産のキャッシュを無効化
    """
    success = ca_industrial_production_service.invalidate_cache()
    return {"success": success}


# ===== Trade Balance (貿易収支) =====

@router.get("/trade-balance")
async def get_ca_trade_balance(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ貿易収支データを取得

    データソース: Statistics Canada Table 12-10-0011-01
    Canadian international merchandise trade

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{
                "date": "YYYY-MM-DD",
                "balance": float,
                "exports": float,
                "imports": float,
                "mom": float,
                "mom_change": float,
                "yoy": float,
                "yoy_change": float
            }, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_trade_balance_service.get_ca_trade_balance_data(force_refresh=force_refresh)


@router.get("/trade-balance/cache")
async def get_ca_trade_balance_cache_status() -> Dict[str, Any]:
    """
    カナダ貿易収支のキャッシュ状態を取得
    """
    return ca_trade_balance_service.get_cache_status()


@router.delete("/trade-balance/cache")
async def invalidate_ca_trade_balance_cache() -> Dict[str, bool]:
    """
    カナダ貿易収支のキャッシュを無効化
    """
    success = ca_trade_balance_service.invalidate_cache()
    return {"success": success}


# ===== Current Account (経常収支) =====

@router.get("/current-account")
async def get_ca_current_account(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ経常収支データを取得

    データソース: Statistics Canada Table 36-10-0018-01
    Balance of international payments, current account

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{
                "date": "YYYY-MM-DD",
                "value": float,
                "qoq_change": float
            }, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_current_account_service.get_ca_current_account_data(force_refresh=force_refresh)


@router.get("/current-account/cache")
async def get_ca_current_account_cache_status() -> Dict[str, Any]:
    """
    カナダ経常収支のキャッシュ状態を取得
    """
    return ca_current_account_service.get_cache_status()


@router.delete("/current-account/cache")
async def invalidate_ca_current_account_cache() -> Dict[str, bool]:
    """
    カナダ経常収支のキャッシュを無効化
    """
    success = ca_current_account_service.invalidate_cache()
    return {"success": success}


# ===== Current Account to GDP Ratio (経常収支対GDP比) =====

@router.get("/current-account-gdp-ratio")
async def get_ca_current_account_gdp_ratio(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ経常収支対GDP比データを取得

    データソース:
    - Statistics Canada Table 36-10-0018-01 (経常収支)
    - Statistics Canada Table 36-10-0104-01 (GDP)

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{
                "date": "YYYY-MM-DD",
                "value": float,
                "current_account": float,
                "gdp": float
            }, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_current_account_gdp_ratio_service.get_ca_current_account_gdp_ratio_data(force_refresh=force_refresh)


@router.get("/current-account-gdp-ratio/cache")
async def get_ca_current_account_gdp_ratio_cache_status() -> Dict[str, Any]:
    """
    カナダ経常収支対GDP比のキャッシュ状態を取得
    """
    return ca_current_account_gdp_ratio_service.get_cache_status()


@router.delete("/current-account-gdp-ratio/cache")
async def invalidate_ca_current_account_gdp_ratio_cache() -> Dict[str, bool]:
    """
    カナダ経常収支対GDP比のキャッシュを無効化
    """
    success = ca_current_account_gdp_ratio_service.invalidate_cache()
    return {"success": success}


# ===== US Export Dependence (対米輸出依存度) =====

@router.get("/us-export-dependence")
async def get_ca_us_export_dependence(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ対米輸出依存度データを取得

    データソース: Statistics Canada Table 12-10-0011-01
    International merchandise trade for all countries and by Principal Trading Partners

    計算方法: 米国向け輸出 / 総輸出 × 100

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{
                "date": "YYYY-MM-DD",
                "value": float,  # 依存度（%）
                "us_export": float,  # 米国向け輸出（M CAD）
                "total_export": float,  # 総輸出（M CAD）
                "mom_change": float  # 前月比増減（pp）
            }, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_us_export_dependence_service.get_ca_us_export_dependence_data(force_refresh=force_refresh)


@router.get("/us-export-dependence/cache")
async def get_ca_us_export_dependence_cache_status() -> Dict[str, Any]:
    """
    カナダ対米輸出依存度のキャッシュ状態を取得
    """
    return ca_us_export_dependence_service.get_cache_status()


@router.delete("/us-export-dependence/cache")
async def invalidate_ca_us_export_dependence_cache() -> Dict[str, bool]:
    """
    カナダ対米輸出依存度のキャッシュを無効化
    """
    success = ca_us_export_dependence_service.invalidate_cache()
    return {"success": success}


# ===== Housing Starts (住宅着工件数) =====

@router.get("/housing-starts")
async def get_ca_housing_starts(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ住宅着工件数データを取得

    データソース: Statistics Canada Table 34-10-0158-01
    Canada Mortgage and Housing Corporation (CMHC)

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{
                "date": "YYYY-MM-DD",
                "value": float,  # 千件（年率換算）
                "mom": float,    # 前月比（%）
                "yoy": float     # 前年比（%）
            }, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_housing_starts_service.get_ca_housing_starts_data(force_refresh=force_refresh)


@router.get("/housing-starts/cache")
async def get_ca_housing_starts_cache_status() -> Dict[str, Any]:
    """
    カナダ住宅着工件数のキャッシュ状態を取得
    """
    return ca_housing_starts_service.get_cache_status()


@router.delete("/housing-starts/cache")
async def invalidate_ca_housing_starts_cache() -> Dict[str, bool]:
    """
    カナダ住宅着工件数のキャッシュを無効化
    """
    success = ca_housing_starts_service.invalidate_cache()
    return {"success": success}


# ===== Building Permits (建築許可) =====

@router.get("/building-permits")
async def get_ca_building_permits(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ建築許可データを取得

    データソース: Statistics Canada Table 34-10-0292-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{
                "date": "YYYY-MM-DD",
                "value": float,  # 百万カナダドル
                "mom": float,    # 前月比（%）
                "yoy": float     # 前年比（%）
            }, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_building_permits_service.get_ca_building_permits_data(force_refresh=force_refresh)


@router.get("/building-permits/cache")
async def get_ca_building_permits_cache_status() -> Dict[str, Any]:
    """
    カナダ建築許可のキャッシュ状態を取得
    """
    return ca_building_permits_service.get_cache_status()


@router.delete("/building-permits/cache")
async def invalidate_ca_building_permits_cache() -> Dict[str, bool]:
    """
    カナダ建築許可のキャッシュを無効化
    """
    success = ca_building_permits_service.invalidate_cache()
    return {"success": success}


# ===== New Housing Price Index (新築住宅価格指数) =====

@router.get("/new-housing-price-index")
async def get_ca_new_housing_price_index(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ新築住宅価格指数（NHPI）データを取得

    データソース: Statistics Canada Table 18-10-0205-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "mom": float, "yoy": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_new_housing_price_index_service.get_ca_new_housing_price_index_data(force_refresh=force_refresh)


@router.get("/new-housing-price-index/cache")
async def get_ca_new_housing_price_index_cache_status() -> Dict[str, Any]:
    """
    カナダ新築住宅価格指数のキャッシュ状態を取得
    """
    return ca_new_housing_price_index_service.get_cache_status()


@router.delete("/new-housing-price-index/cache")
async def invalidate_ca_new_housing_price_index_cache() -> Dict[str, bool]:
    """
    カナダ新築住宅価格指数のキャッシュを無効化
    """
    success = ca_new_housing_price_index_service.invalidate_cache()
    return {"success": success}


# ===== Debt Service Ratio (家計債務返済比率) =====

@router.get("/debt-service-ratio")
async def get_ca_debt_service_ratio(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ家計債務返済比率（DSR）データを取得

    データソース: Statistics Canada Table 11-10-0065-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float, "mortgage": float, "non_mortgage": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_debt_service_ratio_service.get_ca_debt_service_ratio_data(force_refresh=force_refresh)


@router.get("/debt-service-ratio/cache")
async def get_ca_debt_service_ratio_cache_status() -> Dict[str, Any]:
    """
    カナダ家計DSRのキャッシュ状態を取得
    """
    return ca_debt_service_ratio_service.get_cache_status()


@router.delete("/debt-service-ratio/cache")
async def invalidate_ca_debt_service_ratio_cache() -> Dict[str, bool]:
    """
    カナダ家計DSRのキャッシュを無効化
    """
    success = ca_debt_service_ratio_service.invalidate_cache()
    return {"success": success}


# ===== CPI Service / Rent (CPI サービス/家賃) =====

@router.get("/cpi-service-rent")
async def get_ca_cpi_service_rent(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダCPI サービス/家賃（粘着性CPI）データを取得

    データソース: Statistics Canada WDS API (Table 18-10-0004-01)
    - All-items (総合CPI)
    - excl. food and energy (コア)
    - Services (サービス)
    - Shelter (住居)
    - Rent (家賃)

    すべてYoY（前年比）

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "all_items": float, "ex_food_energy": float, "services": float, "shelter": float, "rent": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_cpi_service_rent_service.get_ca_cpi_service_rent_data(force_refresh=force_refresh)


@router.get("/cpi-service-rent/cache")
async def get_ca_cpi_service_rent_cache_status() -> Dict[str, Any]:
    """
    カナダCPI サービス/家賃のキャッシュ状態を取得
    """
    return ca_cpi_service_rent_service.get_cache_status()


@router.delete("/cpi-service-rent/cache")
async def invalidate_ca_cpi_service_rent_cache() -> Dict[str, bool]:
    """
    カナダCPI サービス/家賃のキャッシュを無効化
    """
    success = ca_cpi_service_rent_service.invalidate_cache()
    return {"success": success}


# ===== Job Vacancy Rate (求人率) =====

@router.get("/job-vacancy-rate")
async def get_ca_job_vacancy_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ求人率データを取得

    データソース: Statistics Canada Table 14-10-0432-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_job_vacancy_rate_service.get_ca_job_vacancy_rate_data(force_refresh=force_refresh)


@router.get("/job-vacancy-rate/cache")
async def get_ca_job_vacancy_rate_cache_status() -> Dict[str, Any]:
    """
    カナダ求人率のキャッシュ状態を取得
    """
    return ca_job_vacancy_rate_service.get_cache_status()


@router.delete("/job-vacancy-rate/cache")
async def invalidate_ca_job_vacancy_rate_cache() -> Dict[str, bool]:
    """
    カナダ求人率のキャッシュを無効化
    """
    success = ca_job_vacancy_rate_service.invalidate_cache()
    return {"success": success}


# ===== Ivey PMI =====

@router.get("/ivey-pmi")
async def get_ca_ivey_pmi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ Ivey PMI データを取得

    データソース: Ivey Business School / FMP / DB蓄積

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_ivey_pmi_service.get_ca_ivey_pmi_data(force_refresh=force_refresh)


@router.get("/ivey-pmi/cache")
async def get_ca_ivey_pmi_cache_status() -> Dict[str, Any]:
    """
    カナダ Ivey PMI のキャッシュ状態を取得
    """
    return ca_ivey_pmi_service.get_cache_status()


@router.delete("/ivey-pmi/cache")
async def invalidate_ca_ivey_pmi_cache() -> Dict[str, bool]:
    """
    カナダ Ivey PMI のキャッシュを無効化
    """
    success = ca_ivey_pmi_service.invalidate_cache()
    return {"success": success}


# ===== S&P Global PMI =====

@router.get("/sp-pmi")
async def get_ca_sp_pmi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ S&P Global PMI データを取得（製造業/サービス業/総合）

    データソース: S&P Global / CSV / FMP / DB蓄積
    """
    return ca_sp_pmi_service.get_ca_sp_pmi_data(force_refresh=force_refresh)


@router.get("/sp-pmi/cache")
async def get_ca_sp_pmi_cache_status() -> Dict[str, Any]:
    """
    カナダ S&P Global PMI のキャッシュ状態を取得
    """
    return ca_sp_pmi_service.get_cache_status()


@router.delete("/sp-pmi/cache")
async def invalidate_ca_sp_pmi_cache() -> Dict[str, bool]:
    """
    カナダ S&P Global PMI のキャッシュを無効化
    """
    success = ca_sp_pmi_service.invalidate_cache()
    return {"success": success}
