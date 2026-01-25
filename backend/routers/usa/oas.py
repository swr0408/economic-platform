"""
OAS（Option-Adjusted Spread）APIルーター
日次データ（毎日9:00 AM CST発表）
"""
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

try:
    from backend.services.usa.oas_service import oas_service
except ImportError:
    from services.usa.oas_service import oas_service

router = APIRouter(prefix="/api/usa/frb", tags=["frb"])


@router.get("/oas")
def get_oas(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    OAS（Option-Adjusted Spread）を取得

    3シリーズ:
    - BAMLH0A0HYM2: ICE BofA US High Yield Index OAS
    - BAMLC0A0CM: ICE BofA US Corporate Index OAS
    - BAMLH0A0HYM2EY: ICE BofA US High Yield Index Effective Yield

    日次データ（毎日 9:00 AM CST発表）
    """
    start_time = time.time()

    try:
        result = oas_service.get_data(force_refresh=refresh)

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "hy_spread": result["hy_spread"],
            "ig_spread": result["ig_spread"],
            "hy_yield": result["hy_yield"],
            "latest_hy_spread": result.get("latest_hy_spread"),
            "latest_ig_spread": result.get("latest_ig_spread"),
            "latest_hy_yield": result.get("latest_hy_yield"),
            "next_release": result.get("next_release"),
            "meta": {
                "cached": result.get("cached", False),
                "source": result.get("source", "unknown"),
                "last_updated": result.get("last_updated"),
                "response_time_ms": round(response_time_ms, 2),
                "count": {
                    "hy_spread": len(result["hy_spread"]),
                    "ig_spread": len(result["ig_spread"]),
                    "hy_yield": len(result["hy_yield"]),
                }
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching OAS: {str(e)}"
        )


@router.get("/oas/status")
def get_oas_cache_status() -> Dict[str, Any]:
    """OASのキャッシュ状態を取得"""
    try:
        return oas_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/oas/cache")
def invalidate_oas_cache() -> Dict[str, Any]:
    """OASのキャッシュを無効化"""
    try:
        success = oas_service.invalidate_cache()
        return {
            "success": success,
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
