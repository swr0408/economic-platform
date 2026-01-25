"""
FRB総資産（FRED WALCL）APIルーター
週次データ（毎週水曜日発表）
"""
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

try:
    from backend.services.usa.frb_total_assets_service import frb_total_assets_service
except ImportError:
    from services.usa.frb_total_assets_service import frb_total_assets_service

router = APIRouter(prefix="/api/usa/frb", tags=["frb"])


@router.get("/total-assets")
def get_frb_total_assets(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    FRB総資産（WALCL）を取得

    Federal Reserveのバランスシート総資産
    週次データ（毎週水曜日 3:30 PM ET発表）
    """
    start_time = time.time()

    try:
        result = frb_total_assets_service.get_data(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="FRB Total Assets data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "series_id": "WALCL",
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
            detail=f"Error fetching FRB Total Assets: {str(e)}"
        )


@router.get("/total-assets/status")
def get_frb_total_assets_cache_status() -> Dict[str, Any]:
    """FRB総資産のキャッシュ状態を取得"""
    try:
        return frb_total_assets_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/total-assets/cache")
def invalidate_frb_total_assets_cache() -> Dict[str, Any]:
    """FRB総資産のキャッシュを無効化"""
    try:
        success = frb_total_assets_service.invalidate_cache()
        return {
            "success": success,
            "series_id": "WALCL",
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
