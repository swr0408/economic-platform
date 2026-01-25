"""
機械受注ルーター（日本）
API endpoints for Japan Machinery Orders data (e-Stat API)

Endpoints:
- GET /api/japan/machinery-orders - 機械受注データ取得
- GET /api/japan/machinery-orders/chart - チャート用データ（YoY）
- GET /api/japan/machinery-orders/table - テーブル用データ（MoM）
- GET /api/japan/machinery-orders/cache-status - キャッシュステータス
- POST /api/japan/machinery-orders/refresh - データ強制更新
- DELETE /api/japan/machinery-orders/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import logging

try:
    from backend.services.japan.machinery_orders_service import machinery_orders_service
except ImportError:
    from services.japan.machinery_orders_service import machinery_orders_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/japan", tags=["Japan - Machinery Orders"])


@router.get("/machinery-orders")
async def get_machinery_orders_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    機械受注データを取得（船舶・電力を除く民需）

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        機械受注データ（月次、前月比 % / 前年比 %）
        - data: 時系列データ配列
        - last_updated: 最終更新日時
        - source: データソース
        - next_release: 次回発表日時
    """
    try:
        result = machinery_orders_service.get_machinery_orders_data(force_refresh=force_refresh)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error fetching machinery orders data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/machinery-orders/chart")
async def get_machinery_orders_chart():
    """
    チャート用データを取得（YoY）

    Returns:
        チャート表示用のYoYデータ
    """
    try:
        result = machinery_orders_service.get_chart_data()
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error fetching machinery orders chart data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/machinery-orders/table")
async def get_machinery_orders_table():
    """
    テーブル用データを取得（MoM、新しい順）

    Returns:
        テーブル表示用のMoMデータ
    """
    try:
        result = machinery_orders_service.get_table_data()
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error fetching machinery orders table data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/machinery-orders/cache-status")
async def get_machinery_orders_cache_status():
    """
    キャッシュステータスを取得
    """
    try:
        return machinery_orders_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/machinery-orders/refresh")
async def refresh_machinery_orders_data():
    """
    機械受注データを強制更新
    """
    try:
        result = machinery_orders_service.get_machinery_orders_data(force_refresh=True)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error refreshing machinery orders data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/machinery-orders/cache")
async def invalidate_machinery_orders_cache():
    """
    キャッシュを削除
    """
    try:
        success = machinery_orders_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
