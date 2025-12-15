"""
Federal Reserve H.15 Selected Interest Rates API ルーター
仕様書準拠版: PostgreSQL + Redis キャッシュ
"""
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

try:
    from backend.services.usa.fed_h15_service import fed_h15_service
except ImportError:
    from services.usa.fed_h15_service import fed_h15_service

router = APIRouter(prefix="/api/fed-h15", tags=["fed-h15"])


@router.get("/policy-rate")
def get_policy_rate(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    Federal Funds Policy Rate (政策金利) データを取得

    データ取得の優先順位:
    1. Redis キャッシュ (< 20ms)
    2. PostgreSQL データベース
    3. Federal Reserve API

    Args:
        refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        Policy Rate データ（メタ情報付き）
    """
    start_time = time.time()

    try:
        result = fed_h15_service.get_policy_rate(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="Policy Rate data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "data": result["data"],
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
            detail=f"Error fetching Policy Rate: {str(e)}"
        )


@router.get("/policy-rate/status")
def get_policy_rate_cache_status() -> Dict[str, Any]:
    """
    Policy Rate キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    try:
        return fed_h15_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.post("/policy-rate/refresh")
def refresh_policy_rate_cache() -> Dict[str, Any]:
    """
    Policy Rate キャッシュを強制更新

    Returns:
        更新結果
    """
    start_time = time.time()

    try:
        success = fed_h15_service.refresh_cache()
        response_time_ms = (time.time() - start_time) * 1000

        if success:
            return {
                "success": True,
                "message": "Cache refreshed successfully",
                "response_time_ms": round(response_time_ms, 2)
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to refresh cache"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error refreshing cache: {str(e)}"
        )


@router.delete("/policy-rate/cache")
def invalidate_policy_rate_cache() -> Dict[str, Any]:
    """
    Policy Rate キャッシュを無効化（削除）

    Returns:
        削除結果
    """
    try:
        success = fed_h15_service.invalidate_cache()
        return {
            "success": success,
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
