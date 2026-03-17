"""
韓国半導体輸出 APIルーター

エンドポイント:
- GET /api/global/kr-semiconductor-exports - データ取得
- GET /api/global/kr-semiconductor-exports/cache - キャッシュ状態
- DELETE /api/global/kr-semiconductor-exports/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.kr_semiconductor_exports_service")
kr_semiconductor_exports_service = _mod.kr_semiconductor_exports_service

router = APIRouter(
    prefix="/api/global/kr-semiconductor-exports",
    tags=["global", "economy"]
)


@router.get("")
async def get_kr_semiconductor_exports(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """韓国半導体輸出データを取得"""
    return kr_semiconductor_exports_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
async def get_kr_semiconductor_exports_cache_status() -> Dict[str, Any]:
    """キャッシュ状態を取得"""
    return kr_semiconductor_exports_service.get_cache_status()


@router.delete("/cache")
async def invalidate_kr_semiconductor_exports_cache() -> Dict[str, Any]:
    """キャッシュを無効化"""
    result = kr_semiconductor_exports_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
