"""
BOE GDP Forecast Router
Bank of England GDP成長率見通しのAPIエンドポイント
"""
from fastapi import APIRouter, HTTPException
from typing import Dict
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/boe-gdp-forecast")
async def get_boe_gdp_forecast() -> Dict:
    """
    BOE GDP成長率見通しデータを取得

    Returns:
        Dict containing:
        - table_data: テーブル表示用データ
        - chart_data: チャート表示用データ
        - metadata: ソース情報、予測日、最終更新日
    """
    try:
        from services.uk.boe_gdp_forecast_service import boe_gdp_forecast_service
        data = boe_gdp_forecast_service.fetch_data()
        return data

    except Exception as e:
        logger.error(f"Error fetching BOE GDP forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/boe-gdp-forecast/refresh")
async def refresh_boe_gdp_forecast() -> Dict:
    """
    BOE GDP見通しデータを強制更新

    Returns:
        Dict containing updated data
    """
    try:
        from services.uk.boe_gdp_forecast_service import boe_gdp_forecast_service
        data = boe_gdp_forecast_service.fetch_data(force_refresh=True)
        return {
            "message": "BOE GDP forecast data refreshed successfully",
            "data": data
        }

    except Exception as e:
        logger.error(f"Error refreshing BOE GDP forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))
