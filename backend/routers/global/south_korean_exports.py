"""
韓国輸出（前年比）APIルーター

エンドポイント:
- GET /api/global/south-korean-exports - 韓国輸出データ
- GET /api/global/south-korean-exports/cache - キャッシュ状態
- DELETE /api/global/south-korean-exports/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.south_korean_exports_service")
south_korean_exports_service = _mod.south_korean_exports_service

router = APIRouter(
    prefix="/api/global/south-korean-exports",
    tags=["global", "economy"]
)


@router.get("")
def get_south_korean_exports(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """韓国輸出（前年比）データを取得"""
    return south_korean_exports_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
def get_south_korean_exports_cache_status() -> Dict[str, Any]:
    """韓国輸出のキャッシュ状態を取得"""
    return south_korean_exports_service.get_cache_status()


@router.delete("/cache")
def invalidate_south_korean_exports_cache() -> Dict[str, Any]:
    """韓国輸出のキャッシュを無効化"""
    result = south_korean_exports_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
