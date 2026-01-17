"""
BOE Services Inflation Router
Bank of Englandサービスインフレ指標のAPIエンドポイント
"""
from fastapi import APIRouter, HTTPException
from typing import Dict
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/boe-services-inflation")
async def get_boe_services_inflation() -> Dict:
    """
    BOEサービスインフレデータを取得 (Chart 1.5)

    Returns:
        Dict containing:
        - services_inflation: サービスインフレ指標データ
        - metadata: ソース情報、日付、最終更新日
    """
    try:
        from services.uk.boe_services_inflation_service import boe_services_inflation_service
        data = boe_services_inflation_service.fetch_data()
        return data

    except Exception as e:
        logger.error(f"Error fetching BOE services inflation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/boe-services-inflation/refresh")
async def refresh_boe_services_inflation() -> Dict:
    """
    BOEサービスインフレデータを強制更新

    Returns:
        Dict containing updated data
    """
    try:
        from services.uk.boe_services_inflation_service import boe_services_inflation_service
        data = boe_services_inflation_service.fetch_data(force_refresh=True)
        return data

    except Exception as e:
        logger.error(f"Error refreshing BOE services inflation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
