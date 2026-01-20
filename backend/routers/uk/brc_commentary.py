"""
BRC Commentary Router
Provides API endpoints for BRC Retail Sales Monitor commentary
"""

from fastapi import APIRouter, HTTPException
from services.uk.brc_commentary_service import get_brc_commentary, refresh_brc_commentary

router = APIRouter(
    prefix="/api/uk/brc-commentary",
    tags=["UK Consumer - BRC"]
)


@router.get("")
async def get_commentary():
    """
    Get BRC commentary (cached if available)

    Returns:
        Commentary data with English and Japanese translations
    """
    try:
        data = get_brc_commentary()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch BRC commentary: {str(e)}")


@router.post("/refresh")
async def refresh_commentary():
    """
    Force refresh BRC commentary (bypass cache)

    Returns:
        Fresh commentary data
    """
    try:
        data = refresh_brc_commentary()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh BRC commentary: {str(e)}")
