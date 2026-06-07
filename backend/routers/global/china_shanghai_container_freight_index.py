"""
中国・上海コンテナ運賃指数 APIルーター

エンドポイント:
- GET /api/global/container-freight-index - SCFI/CCFIデータ
- GET /api/global/container-freight-index/cache - キャッシュ状態
- DELETE /api/global/container-freight-index/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.china_shanghai_container_freight_index_service")
china_shanghai_container_freight_index_service = _mod.china_shanghai_container_freight_index_service

router = APIRouter(
    prefix="/api/global/container-freight-index",
    tags=["global", "economy"]
)


@router.get("")
def get_container_freight_index(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """中国・上海コンテナ運賃指数（SCFI/CCFI）データを取得"""
    return china_shanghai_container_freight_index_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
def get_container_freight_index_cache_status() -> Dict[str, Any]:
    """コンテナ運賃指数のキャッシュ状態を取得"""
    return china_shanghai_container_freight_index_service.get_cache_status()


@router.delete("/cache")
def invalidate_container_freight_index_cache() -> Dict[str, Any]:
    """コンテナ運賃指数のキャッシュを無効化"""
    result = china_shanghai_container_freight_index_service.invalidate_cache()
    return {"success": result, "message": "Container Freight Index cache invalidated"}
