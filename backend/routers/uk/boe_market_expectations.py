"""
BOE Market Expectations Router
Bank of England市場金利期待のAPIエンドポイント
"""
from fastapi import APIRouter, HTTPException
from typing import Dict
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/boe-market-expectations")
def get_boe_market_expectations() -> Dict:
    """
    BOE市場金利期待データを取得

    Returns:
        Dict containing:
        - forecasts: 最新と前回の予測データ
        - metadata: ソース情報、日付、最終更新日
    """
    try:
        from services.uk.boe_market_expectations_service import boe_market_expectations_service
        data = boe_market_expectations_service.get_market_expectations()
        return data

    except Exception as e:
        logger.error(f"Error fetching BOE market expectations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/boe-market-expectations/refresh")
def refresh_boe_market_expectations() -> Dict:
    """
    BOE市場金利期待データを強制更新

    Returns:
        Dict containing updated data
    """
    try:
        from services.uk.boe_market_expectations_service import boe_market_expectations_service
        data = boe_market_expectations_service.get_market_expectations(force_refresh=True)
        return data

    except Exception as e:
        logger.error(f"Error refreshing BOE market expectations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
