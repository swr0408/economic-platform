"""
Router for JSCC OIS Curve data

エンドポイント:
- GET /api/japan/ois-curve: JSCC OISカーブデータ取得

データソース: JSCC (Japan Securities Clearing Corporation)
URL: https://www.jpx.co.jp/jscc/en/cimhll0000000umu-att/SettlementRates_{YYYYMMDD}.pdf
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

try:
    from backend.services.japan.ois_curve_service import get_ois_curve_service
except ImportError:
    from services.japan.ois_curve_service import get_ois_curve_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/japan", tags=["japan-ois"])


@router.get("/ois-curve")
def fetch_ois_curve(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetch JSCC OIS Curve data

    Args:
        force_refresh: キャッシュを無視して強制的に最新データを取得

    Returns:
        JSON with:
        - current: {date, data: [{tenor, rate}, ...]}
        - previous: {date, data: [{tenor, rate}, ...]} (for comparison)
        - last_updated: ISO datetime
        - cached: bool
        - source: str
    """
    try:
        logger.info("Fetching JSCC OIS curve data")
        service = get_ois_curve_service()

        # Check if refresh is needed (after 16:00 JST)
        if service.should_refresh() or force_refresh:
            logger.info("Cache refresh needed, fetching fresh data")
            data = service.get_ois_curve(force_refresh=True)
        else:
            data = service.get_ois_curve()

        if 'error' in data and not data.get('current', {}).get('data'):
            raise HTTPException(status_code=500, detail=data['error'])

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OIS curve endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
