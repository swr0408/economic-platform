"""
BOJ Outlook Report API Router

エンドポイント:
- GET /api/japan/boj-outlook: BOJ展望レポートデータ取得

データソース: 日本銀行
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Dict, Any
from pathlib import Path
import logging

from services.japan.boj_outlook_service import get_boj_outlook_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/japan", tags=["japan-boj"])


@router.get("/boj-outlook")
async def fetch_boj_outlook(
    force_refresh: bool = Query(False, description="キャッシュを無視して強制的に最新データを取得")
) -> Dict[str, Any]:
    """
    Fetch BOJ Outlook Report (展望レポート) data

    Returns:
        JSON with report date, PDF URL, image paths for forecasts and risk assessment
    """
    try:
        logger.info("Fetching BOJ Outlook Report data")
        service = get_boj_outlook_service()

        # Check if refresh is needed (monthly check)
        if force_refresh or service.should_refresh():
            logger.info("Cache refresh needed, fetching fresh data")
            data = service.get_outlook_report(force_refresh=True)
        else:
            data = service.get_outlook_report()

        if 'error' in data and not data.get('report_date'):
            raise HTTPException(status_code=500, detail=data['error'])

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in BOJ Outlook endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boj-outlook/image/{image_type}")
async def get_outlook_image(image_type: str):
    """
    Get BOJ Outlook Report image

    Args:
        image_type: 'forecasts' or 'risks'

    Returns:
        PNG image file
    """
    try:
        service = get_boj_outlook_service()
        data = service.get_outlook_report()

        if 'error' in data and not data.get('report_date'):
            raise HTTPException(status_code=404, detail="No outlook report available")

        if image_type == 'forecasts':
            image_path = data.get('forecasts_image')
        elif image_type == 'risks':
            image_path = data.get('risks_image')
        else:
            raise HTTPException(status_code=400, detail="Invalid image type. Use 'forecasts' or 'risks'")

        if not image_path:
            raise HTTPException(status_code=404, detail=f"Image not found for type: {image_type}")

        # Construct full path
        backend_dir = Path(__file__).parent.parent.parent
        full_path = backend_dir / image_path

        if not full_path.exists():
            raise HTTPException(status_code=404, detail=f"Image file not found: {image_path}")

        return FileResponse(
            path=full_path,
            media_type="image/png",
            filename=full_path.name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving outlook image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boj-outlook/cache-status")
async def get_cache_status() -> Dict[str, Any]:
    """Get BOJ Outlook cache status"""
    try:
        service = get_boj_outlook_service()
        return service.get_cache_status()
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
