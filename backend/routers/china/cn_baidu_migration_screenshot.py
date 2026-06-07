"""
中国 百度迁徙（Baidu Migration）人流総量 Screenshot APIルーター

エンドポイント:
- GET /api/china/baidu-migration-screenshot - スクリーンショットURLを取得
- GET /api/china/baidu-migration-screenshot/image - スクリーンショット画像を取得
- POST /api/china/baidu-migration-screenshot/refresh - スクリーンショットを強制更新
- GET /api/china/baidu-migration-screenshot/cache/status - キャッシュ状態を取得
- POST /api/china/baidu-migration-screenshot/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

try:
    from backend.services.china.cn_baidu_migration_screenshot_service import (
        cn_baidu_migration_screenshot_service,
        SCREENSHOT_PATH,
    )
except ImportError:
    from services.china.cn_baidu_migration_screenshot_service import (
        cn_baidu_migration_screenshot_service,
        SCREENSHOT_PATH,
    )


router = APIRouter(
    prefix="/api/china/baidu-migration-screenshot",
    tags=["china", "baidu-migration-screenshot"]
)


@router.get("")
def get_screenshot_url(
    force_refresh: bool = Query(False, description="スクリーンショットを強制更新")
):
    """
    百度迁徙 人流総量のスクリーンショットURL情報を取得

    Args:
        force_refresh: スクリーンショットを強制更新するか

    Returns:
        スクリーンショットURL情報
    """
    if force_refresh:
        result = cn_baidu_migration_screenshot_service.capture_screenshot(force_refresh=True)
        return {
            "screenshot_url": result["url"],
            "last_updated": result["last_updated"],
            "refreshed": True,
        }

    urls = cn_baidu_migration_screenshot_service.get_screenshot_url()
    return {
        "screenshot_url": urls["screenshot_url"],
        "last_updated": urls["last_updated"],
        "refreshed": False,
    }


@router.get("/image")
def get_screenshot_image():
    """
    スクリーンショット画像を取得

    Returns:
        PNG画像ファイル
    """
    if not SCREENSHOT_PATH.exists():
        cn_baidu_migration_screenshot_service.capture_screenshot()

    if SCREENSHOT_PATH.exists():
        return FileResponse(
            SCREENSHOT_PATH,
            media_type="image/png",
            filename="cn_baidu_migration.png"
        )

    return {"error": "Screenshot not available"}


@router.post("/refresh")
def refresh_screenshot():
    """
    スクリーンショットを強制更新

    Returns:
        更新結果
    """
    result = cn_baidu_migration_screenshot_service.capture_screenshot(force_refresh=True)
    return {
        "success": result["success"],
        "url": result["url"],
        "last_updated": result["last_updated"],
    }


@router.get("/cache/status")
def get_cache_status():
    """キャッシュの状態を取得"""
    return cn_baidu_migration_screenshot_service.get_cache_status()


@router.post("/cache/invalidate")
def invalidate_cache():
    """キャッシュを無効化"""
    success = cn_baidu_migration_screenshot_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache",
    }
