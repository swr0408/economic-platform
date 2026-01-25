"""
四半期GDP API Router

エンドポイント:
- GET /api/japan/quarterly-gdp: 前期比（非年率）データ取得
- GET /api/japan/quarterly-gdp/annualized: 前期比年率データ取得
- GET /api/japan/quarterly-gdp/yoy: 前年同期比データ取得
- GET /api/japan/quarterly-gdp/cache-status: キャッシュ状態確認

データソース: 内閣府
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any
import logging

from services.japan.quarterly_gdp_service import get_quarterly_gdp_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/japan", tags=["japan-economy"])


@router.get("/quarterly-gdp")
async def get_quarterly_gdp_qoq(
    force_refresh: bool = Query(False, description="キャッシュを無視して強制的に最新データを取得")
) -> Dict[str, Any]:
    """
    Get Quarterly Real GDP Growth Rate (QoQ) data - 前期比（非年率）

    四半期実質GDP成長率（前期比・非年率）データを取得

    Returns:
        {
            "data": [{"date": "2024-Q1", "value": 0.5}, ...],
            "latest": {"date": "2024-Q3", "value": -0.6},
            "next_release": "ISO datetime",
            "cached": bool,
            "source": "Cabinet Office"
        }
    """
    try:
        service = get_quarterly_gdp_service()
        return service.get_quarterly_gdp_qoq(force_refresh=force_refresh)

    except Exception as e:
        logger.error(f"Error in GDP QoQ endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quarterly-gdp/annualized")
async def get_quarterly_gdp_qoq_annualized(
    force_refresh: bool = Query(False, description="キャッシュを無視して強制的に最新データを取得")
) -> Dict[str, Any]:
    """
    Get Quarterly Real GDP Growth Rate (QoQ Annualized) data - 前期比年率

    四半期実質GDP成長率（前期比年率）データを取得

    Returns:
        {
            "data": [{"date": "2024-Q1", "value": 2.0}, ...],
            "latest": {"date": "2024-Q3", "value": -2.4},
            "next_release": "ISO datetime",
            "cached": bool,
            "source": "Cabinet Office"
        }
    """
    try:
        service = get_quarterly_gdp_service()
        return service.get_quarterly_gdp_qoq_annualized(force_refresh=force_refresh)

    except Exception as e:
        logger.error(f"Error in GDP QoQ Annualized endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quarterly-gdp/yoy")
async def get_quarterly_gdp_yoy(
    force_refresh: bool = Query(False, description="キャッシュを無視して強制的に最新データを取得")
) -> Dict[str, Any]:
    """
    Get Quarterly Real GDP Growth Rate (YoY) data

    四半期実質GDP成長率（前年同期比）データを取得

    Returns:
        {
            "data": [{"date": "2024-Q1", "value": 1.5}, ...],
            "latest": {"date": "2024-Q3", "value": -1.2},
            "next_release": "ISO datetime",
            "cached": bool,
            "source": "e-Stat (Cabinet Office)"
        }
    """
    try:
        service = get_quarterly_gdp_service()
        return service.get_quarterly_gdp_yoy(force_refresh=force_refresh)

    except Exception as e:
        logger.error(f"Error in GDP YoY endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quarterly-gdp/cache-status")
async def get_cache_status() -> Dict[str, Any]:
    """Get GDP cache status"""
    try:
        service = get_quarterly_gdp_service()
        return service.get_cache_status()
    except Exception as e:
        logger.error(f"Error getting GDP cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/quarterly-gdp/cache")
async def invalidate_cache() -> Dict[str, Any]:
    """Invalidate GDP cache"""
    try:
        service = get_quarterly_gdp_service()
        deleted = service.invalidate_cache()
        return {"success": deleted, "message": "GDP cache invalidated" if deleted else "No cache to invalidate"}
    except Exception as e:
        logger.error(f"Error invalidating GDP cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
