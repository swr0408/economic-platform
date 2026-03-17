"""
日銀当座預金残高 APIルーター

エンドポイント:
- GET /api/japan/boj-current-account-balance - データ取得
- GET /api/japan/boj-current-account-balance/cache - キャッシュ状態
- DELETE /api/japan/boj-current-account-balance/cache - キャッシュ無効化
"""
import importlib
from fastapi import APIRouter, Query
from typing import Dict, Any

_mod = importlib.import_module("services.japan.boj_current_account_balance_service")
boj_current_account_balance_service = _mod.boj_current_account_balance_service

router = APIRouter(
    prefix="/api/japan/boj-current-account-balance",
    tags=["Japan - Policy"]
)


@router.get("")
async def get_boj_current_account_balance(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """日銀当座預金残高データを取得"""
    return boj_current_account_balance_service.get_data(force_refresh=force_refresh)


@router.get("/cache")
async def get_cache_status() -> Dict[str, Any]:
    """キャッシュ状態を取得"""
    return boj_current_account_balance_service.get_cache_status()


@router.delete("/cache")
async def invalidate_cache() -> Dict[str, Any]:
    """キャッシュを無効化"""
    result = boj_current_account_balance_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
