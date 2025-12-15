"""
CME FedWatch Tool API ルーター
スクリーンショット方式
"""
import time
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Dict, Any
from pathlib import Path

try:
    from backend.services.usa.cme_fedwatch_screenshot_service import cme_fedwatch_screenshot_service
except ImportError:
    from services.usa.cme_fedwatch_screenshot_service import cme_fedwatch_screenshot_service

router = APIRouter(prefix="/api/fedwatch", tags=["fedwatch"])


@router.get("/screenshot")
def get_screenshot(
    refresh: bool = Query(False, description="強制的にスクリーンショットを更新する")
) -> Dict[str, Any]:
    """
    CME FedWatch スクリーンショット情報を取得

    Returns:
        - image_url: スクリーンショット画像のURL
        - last_updated: 最終更新日時
        - cached: キャッシュから取得したか
    """
    start_time = time.time()

    try:
        result = cme_fedwatch_screenshot_service.get_screenshot(force_refresh=refresh)
        response_time_ms = (time.time() - start_time) * 1000

        return {
            "image_url": result.get("image_url"),
            "last_updated": result.get("last_updated"),
            "cached": result.get("cached", False),
            "source": result.get("source", "unknown"),
            "response_time_ms": round(response_time_ms, 2),
            "error": result.get("error")
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching FedWatch screenshot: {str(e)}"
        )


@router.get("/image")
def get_image():
    """
    FedWatchスクリーンショット画像を直接返す
    """
    try:
        import os
        screenshot_dir = os.getenv("SCREENSHOT_DIR", "/app/screenshots")
        screenshot_path = Path(screenshot_dir) / "fedwatch_latest.png"

        if not screenshot_path.exists():
            # スクリーンショットを取得
            result = cme_fedwatch_screenshot_service.get_screenshot()
            if not result.get("image_url"):
                raise HTTPException(
                    status_code=404,
                    detail="Screenshot not available"
                )

        if screenshot_path.exists():
            return FileResponse(
                screenshot_path,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=1800"}
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="Screenshot file not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error serving screenshot: {str(e)}"
        )


@router.post("/refresh")
def refresh_screenshot() -> Dict[str, Any]:
    """
    スクリーンショットを強制更新
    """
    start_time = time.time()

    try:
        result = cme_fedwatch_screenshot_service.get_screenshot(force_refresh=True)
        response_time_ms = (time.time() - start_time) * 1000

        return {
            "success": result.get("image_url") is not None,
            "image_url": result.get("image_url"),
            "last_updated": result.get("last_updated"),
            "response_time_ms": round(response_time_ms, 2),
            "error": result.get("error")
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error refreshing screenshot: {str(e)}"
        )


@router.get("/status")
def get_cache_status() -> Dict[str, Any]:
    """キャッシュ状態を取得"""
    try:
        return cme_fedwatch_screenshot_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/cache")
def invalidate_cache() -> Dict[str, Any]:
    """キャッシュを無効化"""
    try:
        success = cme_fedwatch_screenshot_service.invalidate_cache()
        return {
            "success": success,
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
