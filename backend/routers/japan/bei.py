"""
Router for 10-Year Inflation-Indexed JGB BEI (Break-Even Inflation) data

エンドポイント:
- GET /api/japan/bei: 10年物価連動国債BEIデータ取得
- GET /api/japan/bei/pdf: BEI PDFファイル取得

データソース: 財務省 (MOF)
URL: https://www.mof.go.jp/jgbs/topics/bond/10year_inflation-indexed/bei.pdf
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import Dict, Any
from pathlib import Path
import logging

try:
    from backend.services.japan.bei_service import bei_service, PDF_FILE
except ImportError:
    from services.japan.bei_service import bei_service, PDF_FILE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/japan", tags=["japan-bei"])


@router.get("/bei")
async def fetch_bei(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetch 10-Year Inflation-Indexed JGB BEI data

    Args:
        force_refresh: キャッシュを無視して強制的に最新データを取得

    Returns:
        JSON with:
        - data: [{date, value}, ...]
        - latest: {date, value}
        - next_release: {date, time_jst, datetime_jst}
        - last_updated: ISO datetime
        - cached: bool
        - source: str
    """
    try:
        logger.info("Fetching 10-Year Inflation-Indexed JGB BEI data")
        data = bei_service.get_bei_data(force_refresh=force_refresh)

        if 'error' in data and not data.get('data'):
            raise HTTPException(status_code=500, detail=data['error'])

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in BEI endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bei/cache-status")
async def get_bei_cache_status() -> Dict[str, Any]:
    """
    Get BEI cache status

    Returns:
        Cache status information
    """
    try:
        return bei_service.get_cache_status()
    except Exception as e:
        logger.error(f"Error getting BEI cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bei/cache")
async def invalidate_bei_cache() -> Dict[str, Any]:
    """
    Invalidate BEI cache

    Returns:
        Result of cache invalidation
    """
    try:
        result = bei_service.invalidate_cache()
        return {"success": result, "message": "Cache invalidated" if result else "Cache not found"}
    except Exception as e:
        logger.error(f"Error invalidating BEI cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bei/pdf")
async def get_bei_pdf():
    """
    Get BEI PDF file

    ローカルに保存されたPDFファイルを返す。
    ファイルが存在しない場合は、最新データを取得（PDFも同時にダウンロードされる）してから返す。

    Returns:
        PDF file response
    """
    try:
        # PDFファイルが存在しない場合、データを取得（PDFも同時にダウンロードされる）
        if not PDF_FILE.exists():
            logger.info("PDF file not found, fetching data to download PDF")
            bei_service.get_bei_data(force_refresh=True)

        # PDFファイルを返す
        if PDF_FILE.exists():
            return FileResponse(
                path=str(PDF_FILE),
                media_type="application/pdf",
                filename="bei.pdf",
                headers={
                    "Content-Disposition": "inline; filename=bei.pdf",
                    "Cache-Control": "public, max-age=3600"
                }
            )
        else:
            raise HTTPException(status_code=404, detail="PDF file not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving BEI PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))
