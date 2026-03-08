"""
USD Fundamental Index APIルーター

エンドポイント:
- GET /api/global/usd-fundamental-index - データ取得
- GET /api/global/usd-fundamental-index/cache - キャッシュ状態
- DELETE /api/global/usd-fundamental-index/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.usd_fundamental_index_service")
usd_fundamental_index_service = _mod.usd_fundamental_index_service

router = APIRouter(
    prefix="/api/global/usd-fundamental-index",
    tags=["global", "forex"]
)


@router.get("")
async def get_usd_fundamental_index_data(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """USD Fundamental Indexデータを取得"""
    return usd_fundamental_index_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
async def get_usd_fundamental_index_cache_status() -> Dict[str, Any]:
    """キャッシュ状態を取得"""
    return usd_fundamental_index_service.get_cache_status()


@router.delete("/cache")
async def invalidate_usd_fundamental_index_cache() -> Dict[str, Any]:
    """キャッシュを無効化"""
    result = usd_fundamental_index_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
