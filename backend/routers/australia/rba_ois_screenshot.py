"""
RBA OIS Screenshot APIルーター

エンドポイント:
- GET /api/australia/rba-ois-screenshot - スクリーンショットURL一覧を取得
- GET /api/australia/rba-ois-screenshot/ois_1m - OIS 1M画像
- GET /api/australia/rba-ois-screenshot/ois_3m - OIS 3M画像
- GET /api/australia/rba-ois-screenshot/ois_6m - OIS 6M画像
- POST /api/australia/rba-ois-screenshot/refresh - 強制更新
- GET /api/australia/rba-ois-screenshot/cache/status - キャッシュ状態
"""
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from services.australia.rba_ois_screenshot_service import (
    rba_ois_screenshot_service,
    SCREENSHOT_PATHS,
)


router = APIRouter(
    prefix="/api/australia/rba-ois-screenshot",
    tags=["australia", "rba-ois-screenshot"],
)


@router.get("")
async def get_screenshot_urls(
    force_refresh: bool = Query(False, description="スクリーンショットを強制更新"),
):
    """
    RBA OISスクリーンショットのURL一覧を取得

    Args:
        force_refresh: スクリーンショットを強制更新するか
    """
    if force_refresh:
        result = rba_ois_screenshot_service.capture_all_screenshots(force_refresh=True)
        return {
            "screenshots": [
                {
                    "key": key,
                    "label": result[key].get("label", key),
                    "url": result[key]["url"],
                    "exists": result[key]["success"],
                }
                for key in ["ois_1m", "ois_3m", "ois_6m"]
                if key in result
            ],
            "last_updated": result["last_updated"],
            "refreshed": True,
        }

    urls = rba_ois_screenshot_service.get_screenshot_urls()
    return {
        "screenshots": urls["screenshots"],
        "last_updated": urls["last_updated"],
        "refreshed": False,
    }


@router.get("/ois_1m")
async def get_ois_1m_screenshot():
    """OIS 1Mスクリーンショット画像を取得"""
    path = SCREENSHOT_PATHS["ois_1m"]
    if not path.exists():
        rba_ois_screenshot_service.capture_all_screenshots()
    if path.exists():
        return FileResponse(path, media_type="image/png", filename="au_ois_1m.png")
    return {"error": "Screenshot not available"}


@router.get("/ois_3m")
async def get_ois_3m_screenshot():
    """OIS 3Mスクリーンショット画像を取得"""
    path = SCREENSHOT_PATHS["ois_3m"]
    if not path.exists():
        rba_ois_screenshot_service.capture_all_screenshots()
    if path.exists():
        return FileResponse(path, media_type="image/png", filename="au_ois_3m.png")
    return {"error": "Screenshot not available"}


@router.get("/ois_6m")
async def get_ois_6m_screenshot():
    """OIS 6Mスクリーンショット画像を取得"""
    path = SCREENSHOT_PATHS["ois_6m"]
    if not path.exists():
        rba_ois_screenshot_service.capture_all_screenshots()
    if path.exists():
        return FileResponse(path, media_type="image/png", filename="au_ois_6m.png")
    return {"error": "Screenshot not available"}


@router.post("/refresh")
async def refresh_screenshots():
    """スクリーンショットを強制更新"""
    result = rba_ois_screenshot_service.capture_all_screenshots(force_refresh=True)
    return {
        "success": all(result[k]["success"] for k in ["ois_1m", "ois_3m", "ois_6m"] if k in result),
        "results": {k: result[k] for k in ["ois_1m", "ois_3m", "ois_6m"] if k in result},
        "last_updated": result["last_updated"],
    }


@router.get("/cache/status")
async def get_cache_status():
    """キャッシュの状態を取得"""
    return rba_ois_screenshot_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """キャッシュを無効化"""
    success = rba_ois_screenshot_service.invalidate_cache()
    return {"success": success}
