"""
法人企業景気予測調査 Router (Business Survey Index - BSI)
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, Optional

try:
    from backend.services.japan.bsi_service import bsi_service
    from backend.services.japan.bsi_comprehensive_service import bsi_comprehensive_service
except ImportError:
    from services.japan.bsi_service import bsi_service
    from services.japan.bsi_comprehensive_service import bsi_comprehensive_service

router = APIRouter(prefix="/api/japan/bsi", tags=["Japan BSI"])


# =============================================================================
# Basic BSI Endpoints (参考-1シート)
# =============================================================================

@router.get("")
async def get_bsi_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get BSI data (法人企業景気予測調査)

    Data source: e-Stat (財務省)

    Returns:
        - data: List of quarterly BSI data points
        - cached: Whether data was served from cache
        - source: Data source (redis/file/e-stat)
        - last_updated: Last update timestamp
    """
    return bsi_service.get_bsi_data(force_refresh=force_refresh)


@router.get("/chart")
async def get_bsi_chart_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get BSI data formatted for chart display

    Returns data with metadata including series information and colors
    """
    return bsi_service.get_chart_data(force_refresh=force_refresh)


@router.get("/table")
async def get_bsi_table_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get BSI data formatted for table display

    Returns recent quarters of BSI data in tabular format
    """
    return bsi_service.get_table_data(force_refresh=force_refresh)


@router.post("/refresh")
async def refresh_bsi_data() -> Dict[str, Any]:
    """Force refresh BSI data from e-Stat"""
    return bsi_service.get_bsi_data(force_refresh=True)


@router.delete("/cache")
async def invalidate_bsi_cache() -> Dict[str, Any]:
    """Invalidate BSI cache"""
    success = bsi_service.invalidate_cache()
    return {"success": success, "message": "Cache invalidated" if success else "Cache invalidation failed"}


# =============================================================================
# Comprehensive BSI Endpoints (全シート対応)
# =============================================================================

@router.get("/sheets")
async def get_sheet_info() -> Dict[str, Any]:
    """
    Get available sheet and period type information

    Returns:
        - sheets: List of available sheets (ref1-ref4)
        - period_types: List of available period types (actual, forecast1, forecast2)
    """
    return bsi_comprehensive_service.get_sheet_info()


@router.get("/{sheet_name}/{period_type}")
async def get_comprehensive_data(
    sheet_name: str,
    period_type: str,
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get BSI data for specific sheet and period type

    Args:
        sheet_name: "ref1", "ref2", "ref3", or "ref4"
        period_type: "actual", "forecast1" (翌期), or "forecast2" (翌々期)
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        Dictionary containing BSI survey data
    """
    valid_sheets = ["ref1", "ref2", "ref3", "ref4"]
    valid_periods = ["actual", "forecast1", "forecast2"]

    if sheet_name not in valid_sheets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sheet_name. Must be one of: {valid_sheets}"
        )

    if period_type not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period_type. Must be one of: {valid_periods}"
        )

    return bsi_comprehensive_service.get_comprehensive_data(
        sheet_name=sheet_name,
        period_type=period_type,
        force_refresh=force_refresh
    )


@router.get("/{sheet_name}/{period_type}/chart")
async def get_comprehensive_chart_data(
    sheet_name: str,
    period_type: str,
    force_refresh: bool = Query(False, description="Force refresh from source")
) -> Dict[str, Any]:
    """
    Get BSI data formatted for chart display

    Args:
        sheet_name: "ref1", "ref2", "ref3", or "ref4"
        period_type: "actual", "forecast1", or "forecast2"
        force_refresh: Force refresh cache

    Returns:
        Chart data and metadata
    """
    valid_sheets = ["ref1", "ref2", "ref3", "ref4"]
    valid_periods = ["actual", "forecast1", "forecast2"]

    if sheet_name not in valid_sheets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sheet_name. Must be one of: {valid_sheets}"
        )

    if period_type not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period_type. Must be one of: {valid_periods}"
        )

    return bsi_comprehensive_service.get_chart_data(
        sheet_name=sheet_name,
        period_type=period_type,
        force_refresh=force_refresh
    )


@router.post("/{sheet_name}/{period_type}/refresh")
async def refresh_comprehensive_data(
    sheet_name: str,
    period_type: str
) -> Dict[str, Any]:
    """Force refresh specific sheet and period type data"""
    return bsi_comprehensive_service.get_comprehensive_data(
        sheet_name=sheet_name,
        period_type=period_type,
        force_refresh=True
    )


@router.delete("/comprehensive/cache")
async def invalidate_comprehensive_cache(
    sheet_name: Optional[str] = Query(None, description="Specific sheet to clear"),
    period_type: Optional[str] = Query(None, description="Specific period type to clear")
) -> Dict[str, Any]:
    """Invalidate comprehensive data cache"""
    success = bsi_comprehensive_service.invalidate_cache(sheet_name, period_type)
    return {"success": success, "message": "Cache invalidated" if success else "Cache invalidation failed"}
