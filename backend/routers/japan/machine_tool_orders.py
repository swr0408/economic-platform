"""
工作機械受注 API Router

エンドポイント:
- GET /api/japan/machine-tool-orders: 工作機械受注データ取得
- GET /api/japan/machine-tool-orders/cache-status: キャッシュ状態確認

データソース: 日本工作機械工業会 (JMTBA)
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any
import logging

from services.japan.machine_tool_orders_service import machine_tool_orders_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/japan", tags=["japan-economy"])


@router.get("/machine-tool-orders")
async def get_machine_tool_orders(
    force_refresh: bool = Query(False, description="キャッシュを無視して強制的に最新データを取得")
) -> Dict[str, Any]:
    """
    Get Machine Tool Orders (YoY) data

    工作機械受注（前年比）データを取得

    Returns:
        {
            "data": [{"date": "2024-01-01", "value": 5.5}, ...],
            "latest": {"date": "2024-12-01", "value": -3.2},
            "next_release": "ISO datetime",
            "cached": bool,
            "source": str
        }
    """
    try:
        return machine_tool_orders_service.get_machine_tool_orders_data(force_refresh=force_refresh)

    except Exception as e:
        logger.error(f"Error in machine tool orders endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/machine-tool-orders/cache-status")
async def get_cache_status() -> Dict[str, Any]:
    """Get machine tool orders cache status"""
    try:
        return machine_tool_orders_service.get_cache_status()
    except Exception as e:
        logger.error(f"Error getting machine tool orders cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/machine-tool-orders/cache")
async def invalidate_cache() -> Dict[str, Any]:
    """Invalidate machine tool orders cache"""
    try:
        deleted = machine_tool_orders_service.invalidate_cache()
        return {"success": deleted, "message": "Machine tool orders cache invalidated" if deleted else "No cache to invalidate"}
    except Exception as e:
        logger.error(f"Error invalidating machine tool orders cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
