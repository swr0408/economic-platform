"""
BOE Unemployment Forecast Router
Bank of England失業率見通しのAPIエンドポイント
"""
from fastapi import APIRouter, HTTPException
from typing import Dict
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/boe-unemployment-forecast")
def get_boe_unemployment_forecast() -> Dict:
    """
    BOE失業率見通しデータを取得

    Returns:
        Dict containing:
        - table_data: テーブル表示用データ
        - chart_data: チャート表示用データ
        - metadata: ソース情報、予測日、最終更新日
    """
    try:
        from services.uk.boe_unemployment_forecast_service import boe_unemployment_forecast_service
        data = boe_unemployment_forecast_service.fetch_data()
        return data

    except Exception as e:
        logger.error(f"Error fetching BOE unemployment forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/boe-unemployment-forecast/refresh")
def refresh_boe_unemployment_forecast() -> Dict:
    """
    BOE失業率見通しデータを強制更新

    Returns:
        Dict containing updated data
    """
    try:
        from services.uk.boe_unemployment_forecast_service import boe_unemployment_forecast_service
        data = boe_unemployment_forecast_service.fetch_data(force_refresh=True)
        return {
            "message": "BOE unemployment forecast data refreshed successfully",
            "data": data
        }

    except Exception as e:
        logger.error(f"Error refreshing BOE unemployment forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))
