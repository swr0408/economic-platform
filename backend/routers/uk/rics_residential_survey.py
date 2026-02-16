"""
RICS UK Residential Market Survey Router
RICS住宅市場調査のAPIエンドポイント
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import Dict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/uk/rics-residential-survey")
async def get_rics_residential_survey() -> Dict:
    """
    RICS住宅市場調査データを取得

    Returns:
        Dict containing:
        - report_date: レポートの対象月
        - pdf_url: 元PDFのURL
        - forecast_image: 予測チャートの画像パス
        - last_updated: 最終更新日時
    """
    try:
        from services.uk.rics_residential_survey_service import rics_residential_survey_service
        data = rics_residential_survey_service.get_survey_report()
        return data

    except Exception as e:
        logger.error(f"Error fetching RICS residential survey: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/uk/rics-residential-survey/refresh")
async def refresh_rics_residential_survey() -> Dict:
    """
    RICS住宅市場調査データを強制更新

    Returns:
        Dict containing updated data
    """
    try:
        from services.uk.rics_residential_survey_service import rics_residential_survey_service
        data = rics_residential_survey_service.get_survey_report(force_refresh=True)
        return data

    except Exception as e:
        logger.error(f"Error refreshing RICS residential survey: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/rics-residential-survey/image/{image_name}")
async def get_rics_survey_image(image_name: str):
    """
    RICS調査の画像を取得

    Args:
        image_name: 画像ファイル名

    Returns:
        PNG画像ファイル
    """
    try:
        # バックエンドディレクトリからの相対パス
        backend_dir = Path(__file__).parent.parent.parent
        image_path = backend_dir / "data" / "cache" / "uk" / "housing" / "rics_survey_images" / image_name

        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")

        # セキュリティチェック: パストラバーサル防止
        image_path = image_path.resolve()
        allowed_dir = (backend_dir / "data" / "cache" / "uk" / "housing" / "rics_survey_images").resolve()
        if not str(image_path).startswith(str(allowed_dir)):
            raise HTTPException(status_code=403, detail="Access denied")

        return FileResponse(image_path, media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving RICS survey image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/uk/rics-residential-survey/status")
async def get_rics_survey_status() -> Dict:
    """
    RICS調査キャッシュ状態を取得

    Returns:
        Dict containing cache status
    """
    try:
        from services.uk.rics_residential_survey_service import rics_residential_survey_service
        return rics_residential_survey_service.get_cache_status()

    except Exception as e:
        logger.error(f"Error getting RICS survey status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
