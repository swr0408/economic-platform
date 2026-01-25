"""
TGA（Treasury General Account）APIルーター
週次データ（毎週水曜日発表）
"""
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

try:
    from backend.services.usa.tga_service import tga_service
except ImportError:
    from services.usa.tga_service import tga_service

router = APIRouter(prefix="/api/usa/frb", tags=["frb"])


@router.get("/tga")
def get_tga(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    TGA（Treasury General Account）を取得

    財務省一般勘定残高
    週次データ（毎週水曜日 3:30 PM ET発表）
    """
    start_time = time.time()

    try:
        result = tga_service.get_data(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="TGA data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "series_id": "WDTGAL",
            "data": result["data"],
            "latest": result.get("latest"),
            "next_release": result.get("next_release"),
            "meta": {
                "cached": result.get("cached", False),
                "source": result.get("source", "unknown"),
                "last_updated": result.get("last_updated"),
                "response_time_ms": round(response_time_ms, 2),
                "count": len(result["data"])
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching TGA: {str(e)}"
        )


@router.get("/tga/status")
def get_tga_cache_status() -> Dict[str, Any]:
    """TGAのキャッシュ状態を取得"""
    try:
        return tga_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/tga/cache")
def invalidate_tga_cache() -> Dict[str, Any]:
    """TGAのキャッシュを無効化"""
    try:
        success = tga_service.invalidate_cache()
        return {
            "success": success,
            "series_id": "WDTGAL",
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
