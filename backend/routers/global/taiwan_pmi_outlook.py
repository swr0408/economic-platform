"""
台湾PMI先行き（電子工学業）APIルーター

エンドポイント:
- GET /api/global/taiwan-pmi-outlook - 台湾PMI先行きデータ
- GET /api/global/taiwan-pmi-outlook/cache - キャッシュ状態
- DELETE /api/global/taiwan-pmi-outlook/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.taiwan_pmi_outlook_service")
taiwan_pmi_outlook_service = _mod.taiwan_pmi_outlook_service

router = APIRouter(
    prefix="/api/global/taiwan-pmi-outlook",
    tags=["global", "economy"]
)


@router.get("")
def get_taiwan_pmi_outlook(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """台湾PMI先行き（電子工学業）データを取得"""
    return taiwan_pmi_outlook_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
def get_taiwan_pmi_outlook_cache_status() -> Dict[str, Any]:
    """台湾PMI先行きのキャッシュ状態を取得"""
    return taiwan_pmi_outlook_service.get_cache_status()


@router.delete("/cache")
def invalidate_taiwan_pmi_outlook_cache() -> Dict[str, Any]:
    """台湾PMI先行きのキャッシュを無効化"""
    result = taiwan_pmi_outlook_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
