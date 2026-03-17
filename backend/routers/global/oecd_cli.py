"""
OECD CLI（景気先行指数）APIルーター

エンドポイント:
- GET /api/global/oecd-cli - データ取得
- GET /api/global/oecd-cli/cache - キャッシュ状態
- DELETE /api/global/oecd-cli/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.global.oecd_cli_service")
oecd_cli_service = _mod.oecd_cli_service

router = APIRouter(
    prefix="/api/global/oecd-cli",
    tags=["global", "economy"]
)


@router.get("")
async def get_oecd_cli(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """OECD CLI（景気先行指数）データを取得"""
    return oecd_cli_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
async def get_oecd_cli_cache_status() -> Dict[str, Any]:
    """キャッシュ状態を取得"""
    return oecd_cli_service.get_cache_status()


@router.delete("/cache")
async def invalidate_oecd_cli_cache() -> Dict[str, Any]:
    """キャッシュを無効化"""
    result = oecd_cli_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
