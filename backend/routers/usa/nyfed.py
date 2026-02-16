"""
NY Fed API ルーター
- ACM Term Premium
- SOFR Volatility
- ON RRP (Overnight Reverse Repo)
"""
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

try:
    from backend.services.usa.nyfed_service import nyfed_term_premium_service
    from backend.services.usa.sofr_volatility_service import sofr_volatility_service
    from backend.services.usa.on_rrp_service import on_rrp_service
except ImportError:
    from services.usa.nyfed_service import nyfed_term_premium_service
    from services.usa.sofr_volatility_service import sofr_volatility_service
    from services.usa.on_rrp_service import on_rrp_service

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


# =============================================================================
# SOFR Volatility Endpoints
# =============================================================================


@router.get("/sofr-volatility")
def get_sofr_volatility(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    SOFR ボラティリティデータを取得

    20日ローリング標準偏差（日次変化のボラティリティ）

    Returns:
        - data: 時系列データ
        - latest: 最新値
        - metadata: メタ情報

    Args:
        refresh: Trueの場合、キャッシュを無視して再取得
    """
    start_time = time.time()

    try:
        result = sofr_volatility_service.get_sofr_volatility_data(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="SOFR Volatility data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "data": result["data"],
            "latest": result.get("latest"),
            "metadata": result.get("metadata", {}),
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
            detail=f"Error fetching SOFR Volatility: {str(e)}"
        )


@router.get("/sofr-volatility/status")
def get_sofr_volatility_cache_status() -> Dict[str, Any]:
    """
    SOFR Volatility キャッシュの状態を取得
    """
    try:
        return sofr_volatility_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/sofr-volatility/cache")
def invalidate_sofr_volatility_cache() -> Dict[str, Any]:
    """
    SOFR Volatility キャッシュを無効化（削除）
    """
    try:
        success = sofr_volatility_service.invalidate_cache()
        return {
            "success": success,
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )


# =============================================================================
# ON RRP (Overnight Reverse Repo) Endpoints
# =============================================================================


@router.get("/on-rrp")
def get_on_rrp(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    ON RRP (Overnight Reverse Repo) 残高データを取得

    Returns:
        - data: 時系列データ
        - latest: 最新値
        - metadata: メタ情報

    Args:
        refresh: Trueの場合、キャッシュを無視して再取得
    """
    start_time = time.time()

    try:
        result = on_rrp_service.get_on_rrp_data(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="ON RRP data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "data": result["data"],
            "latest": result.get("latest"),
            "metadata": result.get("metadata", {}),
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
            detail=f"Error fetching ON RRP: {str(e)}"
        )


@router.get("/on-rrp/status")
def get_on_rrp_cache_status() -> Dict[str, Any]:
    """
    ON RRP キャッシュの状態を取得
    """
    try:
        return on_rrp_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/on-rrp/cache")
def invalidate_on_rrp_cache() -> Dict[str, Any]:
    """
    ON RRP キャッシュを無効化（削除）
    """
    try:
        success = on_rrp_service.invalidate_cache()
        return {
            "success": success,
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
