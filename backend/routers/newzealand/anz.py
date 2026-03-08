"""
ANZ (Australia and New Zealand Banking Group) NZ関連 APIルーター

エンドポイント:
- GET /api/newzealand/anz/business-outlook-price - ANZ企業景況感物価関連メタデータ
- GET /api/newzealand/anz/business-outlook-price/page2 - Page 2 画像
- POST /api/newzealand/anz/business-outlook-price/refresh - 強制再取得
- GET /api/newzealand/anz/business-outlook-price/cache - キャッシュ状態
- DELETE /api/newzealand/anz/business-outlook-price/cache - キャッシュ無効化
- GET /api/newzealand/anz/business-outlook-survey - ANZ企業景況感指数データ
- GET /api/newzealand/anz/business-outlook-survey/cache - キャッシュ状態
- DELETE /api/newzealand/anz/business-outlook-survey/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from typing import Dict, Any

from services.newzealand.nz_anz_business_outlook_price_service import (
    nz_anz_business_outlook_price_service,
)
from services.newzealand.nz_anz_business_outlook_survey_service import (
    nz_anz_business_outlook_survey_service,
)

router = APIRouter(
    prefix="/api/newzealand/anz",
    tags=["newzealand", "inflation"]
)


@router.get("/business-outlook-price")
async def get_business_outlook_price(
    force_refresh: bool = Query(False, description="PDFを強制再取得"),
) -> Dict[str, Any]:
    """ANZ企業景況感物価関連データ（Page 2スクリーンショット）のメタデータを取得"""
    return nz_anz_business_outlook_price_service.get_screenshot_data(
        force_refresh=force_refresh
    )


@router.get("/business-outlook-price/page2")
async def get_page2_image():
    """ANZ Business Outlook Page 2 画像を取得"""
    path = nz_anz_business_outlook_price_service.get_screenshot_path()
    if path and path.exists():
        return FileResponse(path, media_type="image/png", filename="anz_business_outlook_page2.png")
    # 自動取得を試みる
    nz_anz_business_outlook_price_service.get_screenshot_data(force_refresh=True)
    path = nz_anz_business_outlook_price_service.get_screenshot_path()
    if path and path.exists():
        return FileResponse(path, media_type="image/png", filename="anz_business_outlook_page2.png")
    return {"error": "Page 2 image not available"}


@router.post("/business-outlook-price/refresh")
async def refresh_business_outlook_price():
    """PDFを強制再取得してPage 2を更新"""
    nz_anz_business_outlook_price_service.invalidate_cache()
    data = nz_anz_business_outlook_price_service.get_screenshot_data(force_refresh=True)
    return {"success": data.get("page2_exists", False), "data": data}


@router.get("/business-outlook-price/cache")
async def get_business_outlook_price_cache_status() -> Dict[str, Any]:
    """ANZ企業景況感物価関連のキャッシュ状態を取得"""
    return nz_anz_business_outlook_price_service.get_cache_status()


@router.delete("/business-outlook-price/cache")
async def invalidate_business_outlook_price_cache() -> Dict[str, Any]:
    """ANZ企業景況感物価関連のキャッシュを無効化"""
    result = nz_anz_business_outlook_price_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}


# =============================================================================
# ANZ企業景況感指数（Business Confidence）
# =============================================================================

@router.get("/business-outlook-survey")
async def get_business_outlook_survey(
    force_refresh: bool = Query(False, description="データを強制再取得"),
) -> Dict[str, Any]:
    """ANZ企業景況感指数データを取得"""
    return nz_anz_business_outlook_survey_service.get_data(
        force_refresh=force_refresh
    )


@router.get("/business-outlook-survey/cache")
async def get_business_outlook_survey_cache_status() -> Dict[str, Any]:
    """ANZ企業景況感指数のキャッシュ状態を取得"""
    return nz_anz_business_outlook_survey_service.get_cache_status()


@router.delete("/business-outlook-survey/cache")
async def invalidate_business_outlook_survey_cache() -> Dict[str, Any]:
    """ANZ企業景況感指数のキャッシュを無効化"""
    result = nz_anz_business_outlook_survey_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
