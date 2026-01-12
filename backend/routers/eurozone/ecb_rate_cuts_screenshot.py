"""
ECB Rate Cuts Expectation Screenshot APIルーター

エンドポイント:
- GET /api/eurozone/ecb-rate-cuts-screenshot - スクリーンショットURLを取得
- GET /api/eurozone/ecb-rate-cuts-screenshot/refresh - スクリーンショットを強制更新
- GET /api/eurozone/ecb-rate-cuts-screenshot/cache/status - キャッシュ状態を取得
"""
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pathlib import Path

try:
    from backend.services.eurozone.ecb_rate_cuts_screenshot_service import (
        ecb_rate_cuts_screenshot_service,
        YEAREND_SCREENSHOT_PATH,
        RATE_CUTS_SCREENSHOT_PATH
    )
except ImportError:
    from services.eurozone.ecb_rate_cuts_screenshot_service import (
        ecb_rate_cuts_screenshot_service,
        YEAREND_SCREENSHOT_PATH,
        RATE_CUTS_SCREENSHOT_PATH
    )


router = APIRouter(
    prefix="/api/eurozone/ecb-rate-cuts-screenshot",
    tags=["eurozone", "ecb-rate-cuts-screenshot"]
)


@router.get("")
async def get_screenshot_urls(
    force_refresh: bool = Query(False, description="スクリーンショットを強制更新")
):
    """
    ECB利上げ・利下げ期待スクリーンショットのURLを取得

    Args:
        force_refresh: スクリーンショットを強制更新するか

    Returns:
        スクリーンショットURL情報
    """
    if force_refresh:
        result = ecb_rate_cuts_screenshot_service.capture_all_screenshots(force_refresh=True)
        return {
            "yearend_url": result["yearend"]["url"],
            "rate_cuts_url": result["rate_cuts"]["url"],
            "last_updated": result["last_updated"],
            "refreshed": True
        }

    urls = ecb_rate_cuts_screenshot_service.get_screenshot_urls()
    return {
        "yearend_url": urls["yearend_url"],
        "rate_cuts_url": urls["rate_cuts_url"],
        "last_updated": urls["last_updated"],
        "refreshed": False
    }


@router.get("/yearend")
async def get_yearend_screenshot():
    """
    年末金利予想スクリーンショット画像を取得

    Returns:
        PNG画像ファイル
    """
    if not YEAREND_SCREENSHOT_PATH.exists():
        # キャッシュがない場合は取得を試みる
        ecb_rate_cuts_screenshot_service.capture_all_screenshots()

    if YEAREND_SCREENSHOT_PATH.exists():
        return FileResponse(
            YEAREND_SCREENSHOT_PATH,
            media_type="image/png",
            filename="ecb_yearend_rate_expectations.png"
        )

    return {"error": "Screenshot not available"}


@router.get("/rate-cuts")
async def get_rate_cuts_screenshot():
    """
    利上げ・利下げ回数スクリーンショット画像を取得

    Returns:
        PNG画像ファイル
    """
    if not RATE_CUTS_SCREENSHOT_PATH.exists():
        # キャッシュがない場合は取得を試みる
        ecb_rate_cuts_screenshot_service.capture_all_screenshots()

    if RATE_CUTS_SCREENSHOT_PATH.exists():
        return FileResponse(
            RATE_CUTS_SCREENSHOT_PATH,
            media_type="image/png",
            filename="ecb_rate_cuts_expectations.png"
        )

    return {"error": "Screenshot not available"}


@router.post("/refresh")
async def refresh_screenshots():
    """
    スクリーンショットを強制更新

    Returns:
        更新結果
    """
    result = ecb_rate_cuts_screenshot_service.capture_all_screenshots(force_refresh=True)
    return {
        "success": result["yearend"]["success"] and result["rate_cuts"]["success"],
        "yearend": result["yearend"],
        "rate_cuts": result["rate_cuts"],
        "last_updated": result["last_updated"]
    }


@router.get("/cache/status")
async def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return ecb_rate_cuts_screenshot_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = ecb_rate_cuts_screenshot_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
