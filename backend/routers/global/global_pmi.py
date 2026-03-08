"""
Global PMI APIルーター

エンドポイント:
- GET /api/global/pmi/manufacturing - J.P.Morgan Global Manufacturing PMI
- GET /api/global/pmi/manufacturing/cache - キャッシュ状態
- DELETE /api/global/pmi/manufacturing/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.global_manufacturing_pmi_service")
global_manufacturing_pmi_service = _mod.global_manufacturing_pmi_service

router = APIRouter(
    prefix="/api/global/pmi",
    tags=["global", "economy"]
)


@router.get("/manufacturing")
async def get_global_manufacturing_pmi(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """J.P.Morgan Global Manufacturing PMIデータを取得"""
    return global_manufacturing_pmi_service.get_data(force_refresh=force_refresh)


@router.get("/manufacturing/cache")
async def get_manufacturing_pmi_cache_status() -> Dict[str, Any]:
    """J.P.Morgan Global Manufacturing PMIのキャッシュ状態を取得"""
    return global_manufacturing_pmi_service.get_cache_status()


@router.delete("/manufacturing/cache")
async def invalidate_manufacturing_pmi_cache() -> Dict[str, Any]:
    """J.P.Morgan Global Manufacturing PMIのキャッシュを無効化"""
    result = global_manufacturing_pmi_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
