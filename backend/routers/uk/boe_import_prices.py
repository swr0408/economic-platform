"""
BOE Import Prices Router
Bank of England輸入物価・エネルギー価格のAPIエンドポイント
"""
from fastapi import APIRouter, HTTPException
from typing import Dict
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/boe-import-prices")
def get_boe_import_prices() -> Dict:
    """
    BOE輸入物価・エネルギー価格データを取得 (Databank 28/29 + Chart 1.2)

    Returns:
        Dict containing:
        - import_prices: 輸入物価予測データ (Sheet 28)
        - energy_prices: エネルギー価格予測データ (Sheet 29)
        - chart_data: チャートデータ (Chart 1.2)
        - metadata: ソース情報、日付、最終更新日
    """
    try:
        from services.uk.boe_import_prices_service import boe_import_prices_service
        data = boe_import_prices_service.fetch_data()
        return data

    except Exception as e:
        logger.error(f"Error fetching BOE import prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/boe-import-prices/refresh")
def refresh_boe_import_prices() -> Dict:
    """
    BOE輸入物価・エネルギー価格データを強制更新

    Returns:
        Dict containing updated data
    """
    try:
        from services.uk.boe_import_prices_service import boe_import_prices_service
        data = boe_import_prices_service.fetch_data(force_refresh=True)
        return data

    except Exception as e:
        logger.error(f"Error refreshing BOE import prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))
