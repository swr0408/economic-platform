"""
中国クレジットインパルス Screenshot APIルーター

エンドポイント:
- GET /api/china/credit-impulse-screenshot - スクリーンショットURLを取得
- GET /api/china/credit-impulse-screenshot/image - スクリーンショット画像を取得
- POST /api/china/credit-impulse-screenshot/refresh - スクリーンショットを強制更新
- GET /api/china/credit-impulse-screenshot/cache/status - キャッシュ状態を取得
- POST /api/china/credit-impulse-screenshot/cache/invalidate - キャッシュを無効化
"""
import asyncio
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

try:
    from backend.services.china.cn_credit_impulse_screenshot_service import (
        cn_credit_impulse_screenshot_service,
        SCREENSHOT_PATH,
    )
except ImportError:
    from services.china.cn_credit_impulse_screenshot_service import (
        cn_credit_impulse_screenshot_service,
        SCREENSHOT_PATH,
    )


router = APIRouter(
    prefix="/api/china/credit-impulse-screenshot",
    tags=["china", "credit-impulse-screenshot"]
)


@router.get("")
async def get_screenshot_url(
    force_refresh: bool = Query(False, description="スクリーンショットを強制更新")
):
    """
    クレジットインパルスのスクリーンショットURL情報を取得

    ECB rate cuts と同じパターン:
    - capture_screenshot() に常に委譲（キャッシュ/SWR ロジック内蔵）
    - asyncio.to_thread でイベントループをブロックしない
    - キャプチャ失敗時はキャッシュファイルにフォールバック

    Args:
        force_refresh: スクリーンショットを強制更新するか

    Returns:
        スクリーンショットURL情報
    """
    result = await asyncio.to_thread(
        cn_credit_impulse_screenshot_service.capture_screenshot,
        force_refresh=force_refresh,
    )

    screenshot_url = result["url"]

    # キャプチャ失敗時、ディスク上にキャッシュがあればフォールバック
    if not screenshot_url and SCREENSHOT_PATH.exists():
        fallback = cn_credit_impulse_screenshot_service.get_screenshot_url()
        screenshot_url = fallback["screenshot_url"]

    return {
        "screenshot_url": screenshot_url,
        "last_updated": result["last_updated"],
        "refreshed": force_refresh,
    }


@router.get("/image")
async def get_screenshot_image():
    """
    スクリーンショット画像を取得

    Returns:
        PNG画像ファイル
    """
    if not SCREENSHOT_PATH.exists():
        await asyncio.to_thread(
            cn_credit_impulse_screenshot_service.capture_screenshot
        )

    if SCREENSHOT_PATH.exists():
        return FileResponse(
            SCREENSHOT_PATH,
            media_type="image/png",
            filename="cn_credit_impulse.png"
        )

    return {"error": "Screenshot not available"}


@router.post("/refresh")
async def refresh_screenshot():
    """
    スクリーンショットを強制更新

    Returns:
        更新結果
    """
    result = await asyncio.to_thread(
        cn_credit_impulse_screenshot_service.capture_screenshot,
        force_refresh=True,
    )
    return {
        "success": result["success"],
        "url": result["url"],
        "last_updated": result["last_updated"],
    }


@router.get("/cache/status")
async def get_cache_status():
    """キャッシュの状態を取得"""
    return cn_credit_impulse_screenshot_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """キャッシュを無効化"""
    success = cn_credit_impulse_screenshot_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache",
    }
