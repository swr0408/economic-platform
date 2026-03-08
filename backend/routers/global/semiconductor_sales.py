"""
WSTS Semiconductor Sales APIルーター

エンドポイント:
- GET /api/global/semiconductor-sales - データ取得
- GET /api/global/semiconductor-sales/cache - キャッシュ状態
- DELETE /api/global/semiconductor-sales/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.semiconductor_sales_service")
semiconductor_sales_service = _mod.semiconductor_sales_service

router = APIRouter(
    prefix="/api/global/semiconductor-sales",
    tags=["global", "economy"]
)


@router.get("")
async def get_semiconductor_sales_data(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """WSTS半導体売上高データを取得"""
    return semiconductor_sales_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
async def get_semiconductor_sales_cache_status() -> Dict[str, Any]:
    """キャッシュ状態を取得"""
    return semiconductor_sales_service.get_cache_status()


@router.delete("/cache")
async def invalidate_semiconductor_sales_cache() -> Dict[str, Any]:
    """キャッシュを無効化"""
    result = semiconductor_sales_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
