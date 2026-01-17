"""
BOE Inflation Expectations Router
Bank of Englandインフレ期待のAPIエンドポイント
"""
from fastapi import APIRouter, HTTPException
from typing import Dict
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/boe-inflation-expectations")
async def get_boe_inflation_expectations() -> Dict:
    """
    BOEインフレ期待データを取得 (Chart 1.6)

    Returns:
        Dict containing:
        - inflation_expectations: インフレ期待データ
        - metadata: ソース情報、日付、最終更新日
    """
    try:
        from services.uk.boe_inflation_expectations_service import boe_inflation_expectations_service
        data = boe_inflation_expectations_service.fetch_data()
        return data

    except Exception as e:
        logger.error(f"Error fetching BOE inflation expectations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/boe-inflation-expectations/refresh")
async def refresh_boe_inflation_expectations() -> Dict:
    """
    BOEインフレ期待データを強制更新

    Returns:
        Dict containing updated data
    """
    try:
        from services.uk.boe_inflation_expectations_service import boe_inflation_expectations_service
        data = boe_inflation_expectations_service.fetch_data(force_refresh=True)
        return data

    except Exception as e:
        logger.error(f"Error refreshing BOE inflation expectations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
