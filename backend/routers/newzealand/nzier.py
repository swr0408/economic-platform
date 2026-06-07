"""
NZIER (New Zealand Institute of Economic Research) APIルーター

エンドポイント:
- GET /api/newzealand/nzier/business-conditions - NZIER企業景況指数データ
- GET /api/newzealand/nzier/business-conditions/cache - キャッシュ状態
- DELETE /api/newzealand/nzier/business-conditions/cache - キャッシュ無効化
- GET /api/newzealand/nzier/capacity-utilization - 設備稼働率データ
- GET /api/newzealand/nzier/capacity-utilization/cache - キャッシュ状態
- DELETE /api/newzealand/nzier/capacity-utilization/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.newzealand.nz_nzier_business_conditions_index_service import (
    nz_nzier_business_conditions_index_service,
)
from services.newzealand.nz_capacity_utilization_service import (
    nz_capacity_utilization_service,
)

router = APIRouter(
    prefix="/api/newzealand/nzier",
    tags=["newzealand", "consumer"]
)


@router.get("/business-conditions")
def get_business_conditions(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """NZIER企業景況指数データを取得"""
    return nz_nzier_business_conditions_index_service.get_data(
        force_refresh=force_refresh
    )


@router.get("/business-conditions/cache")
def get_business_conditions_cache_status() -> Dict[str, Any]:
    """NZIER企業景況指数のキャッシュ状態を取得"""
    return nz_nzier_business_conditions_index_service.get_cache_status()


@router.delete("/business-conditions/cache")
def invalidate_business_conditions_cache() -> Dict[str, Any]:
    """NZIER企業景況指数のキャッシュを無効化"""
    result = nz_nzier_business_conditions_index_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}


@router.get("/capacity-utilization")
def get_capacity_utilization(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """設備稼働率データを取得"""
    return nz_capacity_utilization_service.get_data(
        force_refresh=force_refresh
    )


@router.get("/capacity-utilization/cache")
def get_capacity_utilization_cache_status() -> Dict[str, Any]:
    """設備稼働率のキャッシュ状態を取得"""
    return nz_capacity_utilization_service.get_cache_status()


@router.delete("/capacity-utilization/cache")
def invalidate_capacity_utilization_cache() -> Dict[str, Any]:
    """設備稼働率のキャッシュを無効化"""
    result = nz_capacity_utilization_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
