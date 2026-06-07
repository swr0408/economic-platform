"""
COMEX 倉庫在庫 (Gold / Silver / Copper) スクリーンショット API ルーター

エンドポイント:
- GET  /api/market/comex-warehouse-screenshot - スクリーンショットURLを取得
- GET  /api/market/comex-warehouse-screenshot/gold - Gold PNG画像
- GET  /api/market/comex-warehouse-screenshot/silver - Silver PNG画像
- GET  /api/market/comex-warehouse-screenshot/copper - Copper PNG画像
- POST /api/market/comex-warehouse-screenshot/refresh - 強制再取得
- GET  /api/market/comex-warehouse-screenshot/cache/status - キャッシュ状態
- POST /api/market/comex-warehouse-screenshot/cache/invalidate - キャッシュ無効化
"""
import asyncio
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

try:
    from backend.services.market.comex_warehouse_screenshot_service import (
        comex_warehouse_screenshot_service,
        GOLD_SCREENSHOT_PATH,
        SILVER_SCREENSHOT_PATH,
        COPPER_SCREENSHOT_PATH,
    )
except ImportError:
    from services.market.comex_warehouse_screenshot_service import (
        comex_warehouse_screenshot_service,
        GOLD_SCREENSHOT_PATH,
        SILVER_SCREENSHOT_PATH,
        COPPER_SCREENSHOT_PATH,
    )


router = APIRouter(
    prefix="/api/market/comex-warehouse-screenshot",
    tags=["market", "comex-warehouse-screenshot"],
)


@router.get("")
async def get_screenshot_urls(
    force_refresh: bool = Query(False, description="スクリーンショットを強制更新")
):
    """COMEX 倉庫在庫スクリーンショットのURLを取得"""
    result = await asyncio.to_thread(
        comex_warehouse_screenshot_service.capture_all_screenshots,
        force_refresh=force_refresh,
    )
    return {
        "gold_url": result["gold"]["url"],
        "silver_url": result["silver"]["url"],
        "copper_url": result["copper"]["url"],
        "last_updated": result["last_updated"],
        "refreshed": force_refresh,
    }


@router.get("/gold")
async def get_gold_screenshot():
    """Gold スクリーンショット PNG"""
    if not GOLD_SCREENSHOT_PATH.exists():
        await asyncio.to_thread(comex_warehouse_screenshot_service.capture_all_screenshots)
    if GOLD_SCREENSHOT_PATH.exists():
        return FileResponse(
            GOLD_SCREENSHOT_PATH,
            media_type="image/png",
            filename="comex_gold_warehouse_stock.png",
        )
    return {"error": "Screenshot not available"}


@router.get("/silver")
async def get_silver_screenshot():
    """Silver スクリーンショット PNG"""
    if not SILVER_SCREENSHOT_PATH.exists():
        await asyncio.to_thread(comex_warehouse_screenshot_service.capture_all_screenshots)
    if SILVER_SCREENSHOT_PATH.exists():
        return FileResponse(
            SILVER_SCREENSHOT_PATH,
            media_type="image/png",
            filename="comex_silver_warehouse_stock.png",
        )
    return {"error": "Screenshot not available"}


@router.get("/copper")
async def get_copper_screenshot():
    """Copper スクリーンショット PNG"""
    if not COPPER_SCREENSHOT_PATH.exists():
        await asyncio.to_thread(comex_warehouse_screenshot_service.capture_all_screenshots)
    if COPPER_SCREENSHOT_PATH.exists():
        return FileResponse(
            COPPER_SCREENSHOT_PATH,
            media_type="image/png",
            filename="comex_copper_warehouse_stock.png",
        )
    return {"error": "Screenshot not available"}


@router.post("/refresh")
async def refresh_screenshots():
    """強制再取得"""
    result = await asyncio.to_thread(
        comex_warehouse_screenshot_service.capture_all_screenshots,
        force_refresh=True,
    )
    return {
        "success": (
            result["gold"]["success"]
            and result["silver"]["success"]
            and result["copper"]["success"]
        ),
        "gold": result["gold"],
        "silver": result["silver"],
        "copper": result["copper"],
        "last_updated": result["last_updated"],
    }


@router.get("/cache/status")
def get_cache_status():
    return comex_warehouse_screenshot_service.get_cache_status()


@router.post("/cache/invalidate")
def invalidate_cache():
    success = comex_warehouse_screenshot_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache",
    }
