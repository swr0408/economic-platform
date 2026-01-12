"""
BOJ Meeting Expectations API Router

エンドポイント:
- GET /api/japan/boj-meeting-expectations: BOJ政策金利期待データ取得

データソース: 東京短資
URL: https://www.tokyotanshi.co.jp/archives/15647
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

try:
    from backend.services.japan.boj_meeting_expectations_service import get_boj_expectations_service
except ImportError:
    from services.japan.boj_meeting_expectations_service import get_boj_expectations_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/japan", tags=["japan-boj"])


@router.get("/boj-meeting-expectations")
async def get_boj_meeting_expectations(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get BOJ meeting expectations data from Tokyo Tanshi

    Args:
        force_refresh: Force refresh cache (default: False)

    Returns:
        {
            "meetings": [
                {
                    "meeting_date": "2026-01-01",
                    "ois_rate": 0.75,
                    "difference": 0.0,
                    "probability": 0.0
                },
                ...
            ],
            "last_updated": "2026-01-09T15:30:00+09:00",
            "source": "https://www.tokyotanshi.co.jp/archives/15647",
            "cached": bool
        }
    """
    try:
        logger.info("Fetching BOJ meeting expectations")
        service = get_boj_expectations_service()

        # Check if refresh is needed
        if not force_refresh and service.should_refresh():
            force_refresh = True

        data = service.get_boj_expectations(force_refresh=force_refresh)

        if 'error' in data and not data.get('meetings'):
            raise HTTPException(status_code=500, detail=data['error'])

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in BOJ meeting expectations endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
