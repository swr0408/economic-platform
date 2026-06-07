"""
オーストラリア統計局（ABS）関連 APIルーター

エンドポイント:
- GET /api/australia/abs/monthly-cpi - 月次CPIデータ
- GET /api/australia/abs/monthly-cpi/cache - キャッシュ状態
- DELETE /api/australia/abs/monthly-cpi/cache - キャッシュ無効化
- GET /api/australia/abs/cpi-categories - CPIカテゴリ別データ
- GET /api/australia/abs/cpi-categories/cache - キャッシュ状態
- DELETE /api/australia/abs/cpi-categories/cache - キャッシュ無効化
- GET /api/australia/abs/quarterly-cpi - 四半期CPIデータ
- GET /api/australia/abs/quarterly-cpi/cache - キャッシュ状態
- DELETE /api/australia/abs/quarterly-cpi/cache - キャッシュ無効化
- GET /api/australia/abs/quarterly-ppi - 四半期PPIデータ
- GET /api/australia/abs/quarterly-ppi/cache - キャッシュ状態
- DELETE /api/australia/abs/quarterly-ppi/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.australia.abs_monthly_cpi_service import abs_monthly_cpi_service
from services.australia.abs_cpi_categories_service import abs_cpi_categories_service
from services.australia.abs_quarterly_cpi_service import abs_quarterly_cpi_service
from services.australia.abs_quarterly_ppi_service import abs_quarterly_ppi_service

router = APIRouter(
    prefix="/api/australia/abs",
    tags=["australia", "inflation"]
)


@router.get("/monthly-cpi")
def get_monthly_cpi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS 月次CPI指標データを取得

    3系列:
    - All groups CPI (季節調整済み) - YoY/MoM
    - Trimmed Mean - YoY/MoM
    - Weighted Median - YoY/MoM
    """
    return abs_monthly_cpi_service.get_monthly_cpi_data(force_refresh=force_refresh)


@router.get("/monthly-cpi/cache")
def get_monthly_cpi_cache_status() -> Dict[str, Any]:
    """月次CPIのキャッシュ状態を取得"""
    return abs_monthly_cpi_service.get_cache_status()


@router.delete("/monthly-cpi/cache")
def invalidate_monthly_cpi_cache() -> Dict[str, bool]:
    """月次CPIのキャッシュを無効化"""
    success = abs_monthly_cpi_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# CPI Categories（カテゴリ別）
# =====================================================================


@router.get("/cpi-categories")
def get_cpi_categories(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS CPIカテゴリ別データを取得

    6系列（前年比 + 前月比）:
    - Goods (財)
    - Services (サービス)
    - Electricity (電力)
    - Rents (家賃)
    - New dwellings (新築住宅)
    - Food & non-alcoholic beverages (食品・非アルコール飲料)
    """
    return abs_cpi_categories_service.get_cpi_categories_data(force_refresh=force_refresh)


@router.get("/cpi-categories/cache")
def get_cpi_categories_cache_status() -> Dict[str, Any]:
    """CPIカテゴリ別のキャッシュ状態を取得"""
    return abs_cpi_categories_service.get_cache_status()


@router.delete("/cpi-categories/cache")
def invalidate_cpi_categories_cache() -> Dict[str, bool]:
    """CPIカテゴリ別のキャッシュを無効化"""
    success = abs_cpi_categories_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# Quarterly CPI（四半期CPI）
# =====================================================================


@router.get("/quarterly-cpi")
def get_quarterly_cpi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS 四半期CPIデータを取得

    5系列:
    - All groups CPI (原系列) — QoQ
    - All groups CPI (原系列) — YoY（Index計算）
    - All groups CPI SA — YoY
    - Trimmed Mean — YoY
    - Weighted Median — YoY
    """
    return abs_quarterly_cpi_service.get_quarterly_cpi_data(force_refresh=force_refresh)


@router.get("/quarterly-cpi/cache")
def get_quarterly_cpi_cache_status() -> Dict[str, Any]:
    """四半期CPIのキャッシュ状態を取得"""
    return abs_quarterly_cpi_service.get_cache_status()


@router.delete("/quarterly-cpi/cache")
def invalidate_quarterly_cpi_cache() -> Dict[str, bool]:
    """四半期CPIのキャッシュを無効化"""
    success = abs_quarterly_cpi_service.invalidate_cache()
    return {"success": success}


# =====================================================================
# Quarterly PPI（四半期PPI）
# =====================================================================


@router.get("/quarterly-ppi")
def get_quarterly_ppi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS 四半期PPIデータを取得

    2系列:
    - PPI QoQ (前期比)
    - PPI YoY (前年比)
    """
    return abs_quarterly_ppi_service.get_quarterly_ppi_data(force_refresh=force_refresh)


@router.get("/quarterly-ppi/cache")
def get_quarterly_ppi_cache_status() -> Dict[str, Any]:
    """四半期PPIのキャッシュ状態を取得"""
    return abs_quarterly_ppi_service.get_cache_status()


@router.delete("/quarterly-ppi/cache")
def invalidate_quarterly_ppi_cache() -> Dict[str, bool]:
    """四半期PPIのキャッシュを無効化"""
    success = abs_quarterly_ppi_service.invalidate_cache()
    return {"success": success}
