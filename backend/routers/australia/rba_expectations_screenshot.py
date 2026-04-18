"""
RBA 利上げ・利下げ期待 Screenshot APIルーター

エンドポイント:
- GET /api/australia/rba-expectations-screenshot - スクリーンショットURL一覧を取得
- GET /api/australia/rba-expectations-screenshot/year_end_rate - Year-End Rate Expectation画像
- GET /api/australia/rba-expectations-screenshot/rate_cuts - Rate Cuts Expectation画像
- POST /api/australia/rba-expectations-screenshot/refresh - 強制更新
- GET /api/australia/rba-expectations-screenshot/cache/status - キャッシュ状態
"""
import asyncio
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from services.australia.rba_expectations_screenshot_service import (
    rba_expectations_screenshot_service,
    SCREENSHOT_PATHS,
)


router = APIRouter(
    prefix="/api/australia/rba-expectations-screenshot",
    tags=["australia", "rba-expectations-screenshot"],
)


@router.get("")
async def get_screenshot_urls(
    force_refresh: bool = Query(False, description="スクリーンショットを強制更新"),
):
    """
    RBA 利上げ・利下げ期待スクリーンショットのURL一覧を取得
    """
    # capture_all_screenshots はブラウザ起動を含む重い同期処理のため
    # asyncio.to_thread でイベントループをブロックしないようにする
    if force_refresh:
        result = await asyncio.to_thread(
            rba_expectations_screenshot_service.capture_all_screenshots, force_refresh=True
        )
        return {
            "screenshots": [
                {
                    "key": key,
                    "label": result[key].get("label", key),
                    "url": result[key]["url"],
                    "exists": result[key]["success"],
                }
                for key in ["year_end_rate", "rate_cuts"]
                if key in result
            ],
            "last_updated": result["last_updated"],
            "refreshed": True,
        }

    urls = rba_expectations_screenshot_service.get_screenshot_urls()
    return {
        "screenshots": urls["screenshots"],
        "last_updated": urls["last_updated"],
        "refreshed": False,
    }


@router.get("/year_end_rate")
async def get_year_end_rate_screenshot():
    """Year-End Rate Expectation スクリーンショット画像を取得"""
    path = SCREENSHOT_PATHS["year_end_rate"]
    if not path.exists():
        await asyncio.to_thread(rba_expectations_screenshot_service.capture_all_screenshots)
    if path.exists():
        return FileResponse(path, media_type="image/png", filename="au_rba_year_end_rate_expectation.png")
    return {"error": "Screenshot not available"}


@router.get("/rate_cuts")
async def get_rate_cuts_screenshot():
    """Rate Cuts Expectation スクリーンショット画像を取得"""
    path = SCREENSHOT_PATHS["rate_cuts"]
    if not path.exists():
        await asyncio.to_thread(rba_expectations_screenshot_service.capture_all_screenshots)
    if path.exists():
        return FileResponse(path, media_type="image/png", filename="au_rba_rate_cuts_expectation.png")
    return {"error": "Screenshot not available"}


@router.post("/refresh")
async def refresh_screenshots():
    """スクリーンショットを強制更新"""
    result = await asyncio.to_thread(
        rba_expectations_screenshot_service.capture_all_screenshots, force_refresh=True
    )
    return {
        "success": all(result[k]["success"] for k in ["year_end_rate", "rate_cuts"] if k in result),
        "results": {k: result[k] for k in ["year_end_rate", "rate_cuts"] if k in result},
        "last_updated": result["last_updated"],
    }


@router.get("/cache/status")
async def get_cache_status():
    """キャッシュの状態を取得"""
    return rba_expectations_screenshot_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """キャッシュを無効化"""
    success = rba_expectations_screenshot_service.invalidate_cache()
    return {"success": success}
