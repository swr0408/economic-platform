"""
ニュージーランド準備銀行（RBNZ）関連 APIルーター

エンドポイント:
- GET /api/newzealand/rbnz/rate - RBNZ政策金利データ
- GET /api/newzealand/rbnz/rate/cache - キャッシュ状態
- DELETE /api/newzealand/rbnz/rate/cache - キャッシュ無効化
- GET /api/newzealand/rbnz/mps-forecast - MPS経済見通しデータ
- GET /api/newzealand/rbnz/mps-forecast/cache - MPS見通しキャッシュ状態
- DELETE /api/newzealand/rbnz/mps-forecast/cache - MPS見通しキャッシュ無効化
- GET /api/newzealand/rbnz/balance-sheet - 中央銀行バランスシート（総資産）
- GET /api/newzealand/rbnz/balance-sheet/cache - バランスシートキャッシュ状態
- DELETE /api/newzealand/rbnz/balance-sheet/cache - バランスシートキャッシュ無効化
- GET /api/newzealand/rbnz/inflation-expectations - インフレ期待
- GET /api/newzealand/rbnz/inflation-expectations/cache - インフレ期待キャッシュ状態
- DELETE /api/newzealand/rbnz/inflation-expectations/cache - インフレ期待キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.newzealand.rbnz_policy_rate_service import rbnz_policy_rate_service
from services.newzealand.rbnz_mps_forecast_service import rbnz_mps_forecast_service
from services.newzealand.nz_central_bank_balance_sheet_service import nz_central_bank_balance_sheet_service
from services.newzealand.nz_bank_balance_sheet_service import nz_bank_balance_sheet_service
from services.newzealand.nz_inflation_expectations_service import nz_inflation_expectations_service

router = APIRouter(
    prefix="/api/newzealand/rbnz",
    tags=["newzealand", "monetary_policy"]
)


@router.get("/rate")
def get_rbnz_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    RBNZ政策金利（OCR）データを取得

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
    return rbnz_policy_rate_service.get_nz_rbnz_rate_data(force_refresh=force_refresh)


@router.get("/rate/cache")
def get_rbnz_rate_cache_status() -> Dict[str, Any]:
    """RBNZ政策金利のキャッシュ状態を取得"""
    return rbnz_policy_rate_service.get_cache_status()


@router.delete("/rate/cache")
def invalidate_rbnz_rate_cache() -> Dict[str, bool]:
    """RBNZ政策金利のキャッシュを無効化"""
    success = rbnz_policy_rate_service.invalidate_cache()
    return {"success": success}


# ===== MPS経済見通し =====

@router.get("/mps-forecast")
def get_mps_forecast(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    RBNZ MPS経済見通しデータを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "indicators": {...},
            "metadata": {...},
            "cached": bool,
            "source": str
        }
    """
    return rbnz_mps_forecast_service.get_nz_economic_forecast_data(force_refresh=force_refresh)


@router.get("/mps-forecast/cache")
def get_mps_forecast_cache_status() -> Dict[str, Any]:
    """MPS経済見通しのキャッシュ状態を取得"""
    return rbnz_mps_forecast_service.get_cache_status()


@router.delete("/mps-forecast/cache")
def invalidate_mps_forecast_cache() -> Dict[str, bool]:
    """MPS経済見通しのキャッシュを無効化"""
    success = rbnz_mps_forecast_service.invalidate_cache()
    return {"success": success}


# ===== 中央銀行バランスシート =====

@router.get("/balance-sheet")
def get_balance_sheet(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    RBNZ中央銀行バランスシート（総資産）データを取得

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
    return nz_central_bank_balance_sheet_service.get_nz_central_bank_balance_sheet_data(
        force_refresh=force_refresh
    )


@router.get("/balance-sheet/cache")
def get_balance_sheet_cache_status() -> Dict[str, Any]:
    """中央銀行バランスシートのキャッシュ状態を取得"""
    return nz_central_bank_balance_sheet_service.get_cache_status()


@router.delete("/balance-sheet/cache")
def invalidate_balance_sheet_cache() -> Dict[str, bool]:
    """中央銀行バランスシートのキャッシュを無効化"""
    success = nz_central_bank_balance_sheet_service.invalidate_cache()
    return {"success": success}


# ===== 銀行バランスシート（S10） =====

@router.get("/bank-balance-sheet")
def get_bank_balance_sheet(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    NZ銀行バランスシート（総資産）データを取得

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
    return nz_bank_balance_sheet_service.get_nz_bank_balance_sheet_data(
        force_refresh=force_refresh
    )


@router.get("/bank-balance-sheet/cache")
def get_bank_balance_sheet_cache_status() -> Dict[str, Any]:
    """銀行バランスシートのキャッシュ状態を取得"""
    return nz_bank_balance_sheet_service.get_cache_status()


@router.delete("/bank-balance-sheet/cache")
def invalidate_bank_balance_sheet_cache() -> Dict[str, bool]:
    """銀行バランスシートのキャッシュを無効化"""
    success = nz_bank_balance_sheet_service.invalidate_cache()
    return {"success": success}


# ===== インフレ期待 =====

@router.get("/inflation-expectations")
def get_inflation_expectations(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """NZインフレ期待（Survey of Expectations）データを取得"""
    return nz_inflation_expectations_service.get_data(force_refresh=force_refresh)


@router.get("/inflation-expectations/cache")
def get_inflation_expectations_cache_status() -> Dict[str, Any]:
    """インフレ期待のキャッシュ状態を取得"""
    return nz_inflation_expectations_service.get_cache_status()


@router.delete("/inflation-expectations/cache")
def invalidate_inflation_expectations_cache() -> Dict[str, bool]:
    """インフレ期待のキャッシュを無効化"""
    success = nz_inflation_expectations_service.invalidate_cache()
    return {"success": success}
