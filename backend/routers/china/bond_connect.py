"""
中国 Bond Connect 関連 APIルーター

エンドポイント:
- GET /api/china/bond-connect/overseas-investor-flow - 海外投資家フローデータ
- GET /api/china/bond-connect/overseas-investor-flow/cache - キャッシュ状態
- DELETE /api/china/bond-connect/overseas-investor-flow/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.china.cn_overseas_investor_flow_service import cn_overseas_investor_flow_service

router = APIRouter(
    prefix="/api/china/bond-connect",
    tags=["china", "bond-connect"]
)


# -------------------------------------------------------------------------
# 海外投資家フロー（Overseas Investor Flow）
# -------------------------------------------------------------------------

@router.get("/overseas-investor-flow")
async def get_overseas_investor_flow(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """海外投資家の中国債券保有残高（SHCH + CCDC）データを返す"""
    return cn_overseas_investor_flow_service.get_data(force_refresh=force_refresh)


@router.get("/overseas-investor-flow/cache")
async def get_overseas_investor_flow_cache_status() -> Dict[str, Any]:
    """海外投資家フローのキャッシュ状態を返す"""
    return cn_overseas_investor_flow_service.get_cache_status()


@router.delete("/overseas-investor-flow/cache")
async def invalidate_overseas_investor_flow_cache() -> Dict[str, Any]:
    """海外投資家フローのキャッシュを無効化"""
    return cn_overseas_investor_flow_service.invalidate_cache()
