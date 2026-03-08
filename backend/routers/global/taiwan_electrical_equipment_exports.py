"""
台湾電気機器輸出APIルーター

エンドポイント:
- GET /api/global/taiwan-electrical-equipment-exports - 台湾電気機器輸出データ
- GET /api/global/taiwan-electrical-equipment-exports/cache - キャッシュ状態
- DELETE /api/global/taiwan-electrical-equipment-exports/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.taiwan_electrical_equipment_exports_service")
taiwan_electrical_equipment_exports_service = _mod.taiwan_electrical_equipment_exports_service

router = APIRouter(
    prefix="/api/global/taiwan-electrical-equipment-exports",
    tags=["global", "economy"]
)


@router.get("")
async def get_taiwan_electrical_equipment_exports(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """台湾電気機器輸出データを取得"""
    return taiwan_electrical_equipment_exports_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
async def get_taiwan_electrical_equipment_exports_cache_status() -> Dict[str, Any]:
    """台湾電気機器輸出のキャッシュ状態を取得"""
    return taiwan_electrical_equipment_exports_service.get_cache_status()


@router.delete("/cache")
async def invalidate_taiwan_electrical_equipment_exports_cache() -> Dict[str, Any]:
    """台湾電気機器輸出のキャッシュを無効化"""
    result = taiwan_electrical_equipment_exports_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
