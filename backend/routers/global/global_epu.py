"""
Global EPU (Economic Policy Uncertainty) APIルーター

エンドポイント:
- GET /api/global/epu - EPUデータ取得 (?series=global|us_monthly|us_daily)
- GET /api/global/epu/cache - キャッシュ状態
- DELETE /api/global/epu/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.global_epu_service")
global_epu_service = _mod.global_epu_service

router = APIRouter(
    prefix="/api/global/epu",
    tags=["global", "economy"]
)


@router.get("")
async def get_epu_data(
    series: str = Query("global", description="シリーズ (global, us_monthly, us_daily)"),
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """EPUデータを取得"""
    return global_epu_service.get_data(series=series, force_refresh=force_refresh)


@router.get("/cache")
async def get_epu_cache_status() -> Dict[str, Any]:
    """EPUキャッシュ状態を取得"""
    return global_epu_service.get_cache_status()


@router.delete("/cache")
async def invalidate_epu_cache() -> Dict[str, Any]:
    """EPUキャッシュを無効化"""
    result = global_epu_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
