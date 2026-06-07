"""
台湾輸出受注（前年比）APIルーター

エンドポイント:
- GET /api/global/taiwan-export-orders - 台湾輸出受注データ
- GET /api/global/taiwan-export-orders/cache - キャッシュ状態
- DELETE /api/global/taiwan-export-orders/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.taiwan_export_orders_service")
taiwan_export_orders_service = _mod.taiwan_export_orders_service

router = APIRouter(
    prefix="/api/global/taiwan-export-orders",
    tags=["global", "economy"]
)


@router.get("")
def get_taiwan_export_orders(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """台湾輸出受注（前年比）データを取得"""
    return taiwan_export_orders_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
def get_taiwan_export_orders_cache_status() -> Dict[str, Any]:
    """台湾輸出受注のキャッシュ状態を取得"""
    return taiwan_export_orders_service.get_cache_status()


@router.delete("/cache")
def invalidate_taiwan_export_orders_cache() -> Dict[str, Any]:
    """台湾輸出受注のキャッシュを無効化"""
    result = taiwan_export_orders_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
