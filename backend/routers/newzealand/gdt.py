"""
GlobalDairyTrade (GDT) APIルーター

エンドポイント:
- GET /api/newzealand/gdt/dairy-trade - GDT乳製品価格指数データ
- GET /api/newzealand/gdt/dairy-trade/cache - キャッシュ状態
- DELETE /api/newzealand/gdt/dairy-trade/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.newzealand.nz_global_dairy_trade_service import (
    nz_global_dairy_trade_service,
)

router = APIRouter(
    prefix="/api/newzealand/gdt",
    tags=["newzealand", "economy"]
)


@router.get("/dairy-trade")
def get_dairy_trade(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """GDT乳製品価格指数データを取得"""
    return nz_global_dairy_trade_service.get_data(force_refresh=force_refresh)


@router.get("/dairy-trade/cache")
def get_dairy_trade_cache_status() -> Dict[str, Any]:
    """GDT乳製品価格指数のキャッシュ状態を取得"""
    return nz_global_dairy_trade_service.get_cache_status()


@router.delete("/dairy-trade/cache")
def invalidate_dairy_trade_cache() -> Dict[str, Any]:
    """GDT乳製品価格指数のキャッシュを無効化"""
    result = nz_global_dairy_trade_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
