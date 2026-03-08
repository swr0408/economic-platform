"""
Komtrax（車両稼働時間）Screenshot APIルーター

エンドポイント:
- GET /api/global/komtrax-screenshot - スクリーンショットURLを取得
- GET /api/global/komtrax-screenshot/image - スクリーンショット画像を取得
- POST /api/global/komtrax-screenshot/refresh - スクリーンショットを強制更新
- GET /api/global/komtrax-screenshot/cache/status - キャッシュ状態を取得
- POST /api/global/komtrax-screenshot/cache/invalidate - キャッシュを無効化
"""
import importlib as _importlib
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

try:
    _mod = _importlib.import_module("backend.services.global.komtrax_screenshot_service")
except ImportError:
    _mod = _importlib.import_module("services.global.komtrax_screenshot_service")
komtrax_screenshot_service = _mod.komtrax_screenshot_service
SCREENSHOT_PATH = _mod.SCREENSHOT_PATH


router = APIRouter(
    prefix="/api/global/komtrax-screenshot",
    tags=["global", "komtrax-screenshot"]
)


@router.get("")
async def get_screenshot_url(
    force_refresh: bool = Query(False, description="スクリーンショットを強制更新")
):
    """
    KomtraxのスクリーンショットURL情報を取得
    """
    if force_refresh:
        result = komtrax_screenshot_service.capture_screenshot(force_refresh=True)
        return {
            "screenshot_url": result["url"],
            "last_updated": result["last_updated"],
            "refreshed": True,
        }

    urls = komtrax_screenshot_service.get_screenshot_url()
    return {
        "screenshot_url": urls["screenshot_url"],
        "last_updated": urls["last_updated"],
        "refreshed": False,
    }


@router.get("/image")
async def get_screenshot_image():
    """
    スクリーンショット画像を取得
    """
    if not SCREENSHOT_PATH.exists():
        raise HTTPException(status_code=404, detail="Screenshot not available. Use refresh endpoint to capture.")

    return FileResponse(
        SCREENSHOT_PATH,
        media_type="image/png",
        filename="komtrax.png"
    )


@router.post("/refresh")
async def refresh_screenshot():
    """
    スクリーンショットを強制更新
    """
    result = komtrax_screenshot_service.capture_screenshot(force_refresh=True)
    return {
        "success": result["success"],
        "url": result["url"],
        "last_updated": result["last_updated"],
    }


@router.get("/cache/status")
async def get_cache_status():
    """キャッシュの状態を取得"""
    return komtrax_screenshot_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """キャッシュを無効化"""
    success = komtrax_screenshot_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache",
    }
