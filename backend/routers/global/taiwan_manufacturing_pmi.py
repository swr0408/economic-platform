"""
台湾製造業PMI（S&P Global）APIルーター

エンドポイント:
- GET /api/global/taiwan-manufacturing-pmi - 台湾製造業PMIデータ
- GET /api/global/taiwan-manufacturing-pmi/cache - キャッシュ状態
- DELETE /api/global/taiwan-manufacturing-pmi/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.taiwan_manufacturing_pmi_service")
taiwan_manufacturing_pmi_service = _mod.taiwan_manufacturing_pmi_service

router = APIRouter(
    prefix="/api/global/taiwan-manufacturing-pmi",
    tags=["global", "economy"]
)


@router.get("")
def get_taiwan_manufacturing_pmi(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """台湾製造業PMI（S&P Global）データを取得"""
    return taiwan_manufacturing_pmi_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
def get_taiwan_manufacturing_pmi_cache_status() -> Dict[str, Any]:
    """台湾製造業PMIのキャッシュ状態を取得"""
    return taiwan_manufacturing_pmi_service.get_cache_status()


@router.delete("/cache")
def invalidate_taiwan_manufacturing_pmi_cache() -> Dict[str, Any]:
    """台湾製造業PMIのキャッシュを無効化"""
    result = taiwan_manufacturing_pmi_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
