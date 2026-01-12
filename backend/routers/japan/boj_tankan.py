"""
BOJ Tankan Router
日銀短観 API endpoints
"""
from fastapi import APIRouter, Query
from typing import Dict, Any, Optional

try:
    from backend.services.japan.boj_tankan_service import boj_tankan_service
    from backend.services.japan.boj_tankan_comprehensive_service import boj_tankan_comprehensive_service
except ImportError:
    from services.japan.boj_tankan_service import boj_tankan_service
    from services.japan.boj_tankan_comprehensive_service import boj_tankan_comprehensive_service

router = APIRouter(prefix="/api/japan/boj-tankan", tags=["Japan BOJ Tankan"])


# =============================================================================
# DI (業況判断指数) Endpoints
# =============================================================================

@router.get("")
async def get_tankan_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get BOJ Tankan DI data (大企業業況判断指数)

    Data source: Bank of Japan
    Excel URL pattern: https://www.boj.or.jp/statistics/tk/zenyo/2021/data/all{YY}{QQ}a.xlsx

    Returns:
        - data: List of DI data with manufacturing/non-manufacturing current/outlook values
        - cached: Whether data was served from cache
        - source: Data source (redis/file/boj)
        - last_updated: Last update timestamp
    """
    return boj_tankan_service.get_tankan_data(force_refresh=force_refresh)


@router.get("/chart")
async def get_tankan_chart_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get BOJ Tankan DI data formatted for chart display

    Returns data with metadata including series information and colors
    """
    return boj_tankan_service.get_tankan_chart_data(force_refresh=force_refresh)


@router.post("/refresh")
async def refresh_tankan_data() -> Dict[str, Any]:
    """Force refresh BOJ Tankan DI data from BOJ"""
    return boj_tankan_service.get_tankan_data(force_refresh=True)


@router.delete("/cache")
async def invalidate_tankan_cache() -> Dict[str, Any]:
    """Invalidate BOJ Tankan DI cache"""
    success = boj_tankan_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Cache invalidation failed"}


@router.get("/cache-status")
async def get_tankan_cache_status() -> Dict[str, Any]:
    """Get cache status for BOJ Tankan DI data"""
    return boj_tankan_service.get_cache_status()


# =============================================================================
# Comprehensive Data Endpoints
# =============================================================================

@router.get("/comprehensive/types")
async def get_comprehensive_data_types() -> Dict[str, Any]:
    """
    Get list of available comprehensive data types

    Returns:
        - capital_investment: 設備投資計画
        - production_facilities: 生産・営業用設備判断
        - employment: 雇用人員判断
        - purchase_price: 仕入価格判断
        - selling_price: 販売価格判断
    """
    return boj_tankan_comprehensive_service.get_all_data_types()


# NOTE: table endpoint must come BEFORE the generic {data_type} endpoint
# to avoid "table" being matched as a data_type
@router.get("/comprehensive/table/{data_type}")
async def get_comprehensive_table_data(
    data_type: str,
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get BOJ Tankan comprehensive data formatted for table display

    Args:
        data_type: One of capital_investment, production_facilities, employment,
                   purchase_price, selling_price

    Returns:
        - table_data: List of data points sorted by date descending
        - metadata: Table metadata including title, source, series info
    """
    return boj_tankan_comprehensive_service.get_table_data(
        data_type=data_type,
        force_refresh=force_refresh
    )


@router.get("/comprehensive/{data_type}")
async def get_comprehensive_data(
    data_type: str,
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get BOJ Tankan comprehensive data for specific type

    Args:
        data_type: One of capital_investment, production_facilities, employment,
                   purchase_price, selling_price

    Returns:
        - data: List of data points
        - name: Data type name in Japanese
        - unit: Data unit
        - cached: Whether data was served from cache
        - source: Data source
    """
    return boj_tankan_comprehensive_service.get_comprehensive_data(
        data_type=data_type,
        force_refresh=force_refresh
    )


@router.post("/comprehensive/{data_type}/refresh")
async def refresh_comprehensive_data(data_type: str) -> Dict[str, Any]:
    """Force refresh specific comprehensive data type"""
    return boj_tankan_comprehensive_service.get_comprehensive_data(
        data_type=data_type,
        force_refresh=True
    )


@router.delete("/comprehensive/cache")
async def invalidate_comprehensive_cache(
    data_type: Optional[str] = Query(None, description="Specific data type to clear, or all if not specified")
) -> Dict[str, Any]:
    """Invalidate comprehensive data cache"""
    success = boj_tankan_comprehensive_service.invalidate_cache(data_type)
    return {"success": success, "message": "Cache invalidated" if success else "Cache invalidation failed"}


@router.get("/comprehensive/cache-status")
async def get_comprehensive_cache_status(
    data_type: Optional[str] = Query(None, description="Specific data type to check")
) -> Dict[str, Any]:
    """Get cache status for comprehensive data"""
    return boj_tankan_comprehensive_service.get_cache_status(data_type)
