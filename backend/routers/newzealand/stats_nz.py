"""
Stats NZ関連 APIルーター

エンドポイント:
- GET /api/newzealand/stats-nz/ppi - PPI（生産者物価指数）データ
- GET /api/newzealand/stats-nz/ppi/cache - PPIキャッシュ状態
- DELETE /api/newzealand/stats-nz/ppi/cache - PPIキャッシュ無効化
- GET /api/newzealand/stats-nz/cpi - CPI（消費者物価指数）データ
- GET /api/newzealand/stats-nz/cpi/cache - CPIキャッシュ状態
- DELETE /api/newzealand/stats-nz/cpi/cache - CPIキャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.newzealand.nz_ppi_service import nz_ppi_service
from services.newzealand.nz_cpi_service import nz_cpi_service
from services.newzealand.nz_cpi_item_service import nz_cpi_item_service
from services.newzealand.nz_traded_nontraded_service import nz_traded_nontraded_service

router = APIRouter(
    prefix="/api/newzealand/stats-nz",
    tags=["newzealand", "inflation"]
)


@router.get("/ppi")
async def get_ppi(
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
async def get_ppi_cache_status() -> Dict[str, Any]:
    """PPIのキャッシュ状態を取得"""
    return nz_ppi_service.get_cache_status()


@router.delete("/ppi/cache")
async def invalidate_ppi_cache() -> Dict[str, bool]:
    """PPIのキャッシュを無効化"""
    success = nz_ppi_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# CPI（消費者物価指数）
# =============================================================================

@router.get("/cpi")
async def get_cpi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ消費者物価指数（CPI）データを取得"""
    return nz_cpi_service.get_nz_cpi_data(force_refresh=force_refresh)


@router.get("/cpi/cache")
async def get_cpi_cache_status() -> Dict[str, Any]:
    """CPIのキャッシュ状態を取得"""
    return nz_cpi_service.get_cache_status()


@router.delete("/cpi/cache")
async def invalidate_cpi_cache() -> Dict[str, bool]:
    """CPIのキャッシュを無効化"""
    success = nz_cpi_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# CPI項目別
# =============================================================================

@router.get("/cpi-item")
async def get_cpi_item(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ CPI項目別データを取得"""
    return nz_cpi_item_service.get_nz_cpi_item_data(force_refresh=force_refresh)


@router.get("/cpi-item/cache")
async def get_cpi_item_cache_status() -> Dict[str, Any]:
    """CPI項目別のキャッシュ状態を取得"""
    return nz_cpi_item_service.get_cache_status()


@router.delete("/cpi-item/cache")
async def invalidate_cpi_item_cache() -> Dict[str, bool]:
    """CPI項目別のキャッシュを無効化"""
    success = nz_cpi_item_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 貿易財/非貿易財
# =============================================================================

@router.get("/traded-nontraded")
async def get_traded_nontraded(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZ 貿易財/非貿易財データを取得"""
    return nz_traded_nontraded_service.get_data(force_refresh=force_refresh)


@router.get("/traded-nontraded/cache")
async def get_traded_nontraded_cache_status() -> Dict[str, Any]:
    """貿易財/非貿易財のキャッシュ状態を取得"""
    return nz_traded_nontraded_service.get_cache_status()


@router.delete("/traded-nontraded/cache")
async def invalidate_traded_nontraded_cache() -> Dict[str, bool]:
    """貿易財/非貿易財のキャッシュを無効化"""
    success = nz_traded_nontraded_service.invalidate_cache()
    return {"success": success}
