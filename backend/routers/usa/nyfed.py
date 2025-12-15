"""
NY Fed ACM Term Premium API ルーター
仕様書準拠版: Redis キャッシュ
"""
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

try:
    from backend.services.usa.nyfed_service import nyfed_term_premium_service
except ImportError:
    from services.usa.nyfed_service import nyfed_term_premium_service

router = APIRouter(prefix="/api/nyfed", tags=["nyfed"])


@router.get("/term-premium")
def get_term_premium(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    ACM タームプレミアム関連データを取得（複数シリーズ）

    Adrian, Crump, and Moench (ACM) モデルに基づく推定値

    Returns:
        - yield_10y: 10年債利回り
        - term_premium: ACMタームプレミアム
        - expected_rate: 期待短期金利

    Args:
        refresh: Trueの場合、キャッシュを無視して再取得
    """
    start_time = time.time()

    try:
        result = nyfed_term_premium_service.get_term_premium_data(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="Term Premium data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "data": result["data"],
            "meta": {
                "cached": result.get("cached", False),
                "source": result.get("source", "unknown"),
                "last_updated": result.get("last_updated"),
                "response_time_ms": round(response_time_ms, 2),
                "count": len(result["data"]),
                "series": ["yield_10y", "term_premium", "expected_rate"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching Term Premium: {str(e)}"
        )


@router.get("/term-premium/status")
def get_term_premium_cache_status() -> Dict[str, Any]:
    """
    Term Premium キャッシュの状態を取得
    """
    try:
        return nyfed_term_premium_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/term-premium/cache")
def invalidate_term_premium_cache() -> Dict[str, Any]:
    """
    Term Premium キャッシュを無効化（削除）
    """
    try:
        success = nyfed_term_premium_service.invalidate_cache()
        return {
            "success": success,
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
