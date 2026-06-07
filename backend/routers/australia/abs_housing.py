"""
オーストラリア住宅関連 APIルーター

エンドポイント:
- GET /api/australia/housing/cotality-home-prices - Cotality住宅価格指数データ
- GET /api/australia/housing/cotality-home-prices/cache - キャッシュ状態
- DELETE /api/australia/housing/cotality-home-prices/cache - キャッシュ無効化
- GET /api/australia/housing/building-permits - 建築許可件数データ
- GET /api/australia/housing/building-permits/cache - キャッシュ状態
- DELETE /api/australia/housing/building-permits/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.australia.au_cotality_home_prices_service import au_cotality_home_prices_service
from services.australia.au_number_of_building_permits_service import au_number_of_building_permits_service

router = APIRouter(
    prefix="/api/australia/housing",
    tags=["australia", "housing"]
)


@router.get("/cotality-home-prices")
def get_cotality_home_prices(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    Cotality住宅価格指数データを取得

    都市別Daily Home Value Index:
    - sydney, melbourne, brisbane, adelaide, perth, aggregate (5 Capital City)
    - 各都市のMoM%（月次）、YoY%（月次）も含む
    """
    return au_cotality_home_prices_service.get_au_cotality_home_prices_data(force_refresh=force_refresh)


@router.get("/cotality-home-prices/cache")
def get_cotality_home_prices_cache_status() -> Dict[str, Any]:
    """Cotality住宅価格指数のキャッシュ状態を取得"""
    return au_cotality_home_prices_service.get_cache_status()


@router.delete("/cotality-home-prices/cache")
def invalidate_cotality_home_prices_cache() -> Dict[str, bool]:
    """Cotality住宅価格指数のキャッシュを無効化"""
    success = au_cotality_home_prices_service.invalidate_cache()
    return {"success": success}


# ===== 建築許可件数 =====

@router.get("/building-permits")
def get_building_permits(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    建築許可件数データを取得

    ABS Series ID: A422070J
    - Total dwelling units, Total (Type of Building), Total Sectors
    - Seasonally Adjusted
    """
    return au_number_of_building_permits_service.get_au_number_of_building_permits_data(force_refresh=force_refresh)


@router.get("/building-permits/cache")
def get_building_permits_cache_status() -> Dict[str, Any]:
    """建築許可件数のキャッシュ状態を取得"""
    return au_number_of_building_permits_service.get_cache_status()


@router.delete("/building-permits/cache")
def invalidate_building_permits_cache() -> Dict[str, bool]:
    """建築許可件数のキャッシュを無効化"""
    success = au_number_of_building_permits_service.invalidate_cache()
    return {"success": success}
