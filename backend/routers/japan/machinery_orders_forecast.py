"""
機械受注見通しルーター（日本）
API endpoints for Japan Machinery Orders Forecast data (e-Stat API)

Endpoints:
- GET /api/japan/machinery-orders-forecast - 機械受注見通しデータ取得
- POST /api/japan/machinery-orders-forecast/refresh - データ強制更新
"""

from fastapi import APIRouter, HTTPException
from typing import Dict
from datetime import datetime
import logging

try:
    from backend.services.japan.machinery_orders_forecast_service import machinery_orders_forecast_service
except ImportError:
    from services.japan.machinery_orders_forecast_service import machinery_orders_forecast_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/japan", tags=["Japan - Machinery Orders Forecast"])


@router.get("/machinery-orders-forecast")
def get_machinery_orders_forecast() -> Dict:
    """
    機械受注見通しデータを取得（四半期）

    Returns:
        達成率、実績額、見通し額のテーブルデータ
    """
    try:
        data = machinery_orders_forecast_service.get_forecast_data()

        return {
            "table_data": data,
            "last_updated": datetime.now().isoformat(),
            "data_source": "e-Stat (Cabinet Office)"
        }

    except Exception as e:
        logger.error(f"Error fetching machinery orders forecast data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/machinery-orders-forecast/refresh")
def refresh_machinery_orders_forecast() -> Dict:
    """
    機械受注見通しデータを強制更新
    """
    try:
        result = machinery_orders_forecast_service.refresh_data()
        return result

    except Exception as e:
        logger.error(f"Error refreshing machinery orders forecast data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
