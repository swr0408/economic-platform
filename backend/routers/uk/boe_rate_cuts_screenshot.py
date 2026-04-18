"""
BOE Rate Cuts Expectation Screenshot APIルーター

エンドポイント:
- GET /api/uk/boe-rate-cuts-screenshot - スクリーンショットURLを取得
- GET /api/uk/boe-rate-cuts-screenshot/yearend - 年末金利予想画像
- GET /api/uk/boe-rate-cuts-screenshot/rate-cuts - 利下げ回数画像
- POST /api/uk/boe-rate-cuts-screenshot/refresh - 強制更新
- GET /api/uk/boe-rate-cuts-screenshot/cache/status - キャッシュ状態
- POST /api/uk/boe-rate-cuts-screenshot/cache/invalidate - キャッシュ無効化
"""
import asyncio
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

try:
    from backend.services.uk.boe_rate_cuts_screenshot_service import (
        boe_rate_cuts_screenshot_service,
        YEAREND_SCREENSHOT_PATH,
        RATE_CUTS_SCREENSHOT_PATH
    )
except ImportError:
    from services.uk.boe_rate_cuts_screenshot_service import (
        boe_rate_cuts_screenshot_service,
        YEAREND_SCREENSHOT_PATH,
        RATE_CUTS_SCREENSHOT_PATH
    )


router = APIRouter(
    prefix="/api/uk/boe-rate-cuts-screenshot",
    tags=["uk", "boe-rate-cuts-screenshot"]
)


@router.get("")
async def get_screenshot_urls(
    force_refresh: bool = Query(False, description="スクリーンショットを強制更新")
):
    result = await asyncio.to_thread(
        boe_rate_cuts_screenshot_service.capture_all_screenshots,
        force_refresh=force_refresh,
    )
    return {
        "yearend_url": result["yearend"]["url"],
        "rate_cuts_url": result["rate_cuts"]["url"],
        "last_updated": result["last_updated"],
        "refreshed": force_refresh,
    }


@router.get("/yearend")
async def get_yearend_screenshot():
    if not YEAREND_SCREENSHOT_PATH.exists():
        await asyncio.to_thread(
            boe_rate_cuts_screenshot_service.capture_all_screenshots
        )

    if YEAREND_SCREENSHOT_PATH.exists():
        return FileResponse(
            YEAREND_SCREENSHOT_PATH,
            media_type="image/png",
            filename="boe_yearend_rate_expectations.png"
        )

    return {"error": "Screenshot not available"}


@router.get("/rate-cuts")
async def get_rate_cuts_screenshot():
    if not RATE_CUTS_SCREENSHOT_PATH.exists():
        await asyncio.to_thread(
            boe_rate_cuts_screenshot_service.capture_all_screenshots
        )

    if RATE_CUTS_SCREENSHOT_PATH.exists():
        return FileResponse(
            RATE_CUTS_SCREENSHOT_PATH,
            media_type="image/png",
            filename="boe_rate_cuts_expectations.png"
        )

    return {"error": "Screenshot not available"}


@router.post("/refresh")
async def refresh_screenshots():
    result = await asyncio.to_thread(
        boe_rate_cuts_screenshot_service.capture_all_screenshots,
        force_refresh=True,
    )
    return {
        "success": result["yearend"]["success"] and result["rate_cuts"]["success"],
        "yearend": result["yearend"],
        "rate_cuts": result["rate_cuts"],
        "last_updated": result["last_updated"]
    }


@router.get("/cache/status")
async def get_cache_status():
    return boe_rate_cuts_screenshot_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    success = boe_rate_cuts_screenshot_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
