"""
BOE CPI Projections Router
Bank of England CPIインフレ見通しのAPIエンドポイント
"""
from fastapi import APIRouter, HTTPException
from typing import Dict
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/boe-cpi-projections")
async def get_boe_cpi_projections() -> Dict:
    """
    BOE CPI見通しデータを取得

    Returns:
        Dict containing:
        - projections: 最新と前回の見通しデータ（Skew値を含む）
        - metadata: ソース情報、日付、最終更新日
    """
    try:
        from services.uk.boe_cpi_projections_service import boe_cpi_projections_service
        data = boe_cpi_projections_service.get_cpi_projections()
        return data

    except Exception as e:
        logger.error(f"Error fetching BOE CPI projections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/boe-cpi-projections/refresh")
async def refresh_boe_cpi_projections() -> Dict:
    """
    BOE CPI見通しデータを強制更新

    Returns:
        Dict containing updated data
    """
    try:
        from services.uk.boe_cpi_projections_service import boe_cpi_projections_service
        data = boe_cpi_projections_service.get_cpi_projections(force_refresh=True)
        return data

    except Exception as e:
        logger.error(f"Error refreshing BOE CPI projections: {e}")
        raise HTTPException(status_code=500, detail=str(e))
