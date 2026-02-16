"""
FRED (Federal Reserve Economic Data) API ルーター
- KWタームプレミアム（THREEFYTP10）
- CREローン延滞率（DRCRELEXFACBS等）
"""
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

try:
    from backend.services.usa.fred_service import fred_service
    from backend.services.usa.cre_loan_delinquency_service import cre_loan_delinquency_service
except ImportError:
    from services.usa.fred_service import fred_service
    from services.usa.cre_loan_delinquency_service import cre_loan_delinquency_service

router = APIRouter(prefix="/api/fred", tags=["fred"])


@router.get("/kw-term-premium")
def get_kw_term_premium(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    KWモデル タームプレミアム（THREEFYTP10）を取得

    Kim-Wright モデルに基づく10年タームプレミアム推定値
    """
    start_time = time.time()

    try:
        result = fred_service.get_kw_term_premium(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="KW Term Premium data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "series_id": "THREEFYTP10",
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
            detail=f"Error fetching KW Term Premium: {str(e)}"
        )


@router.get("/kw-term-premium/status")
def get_kw_cache_status() -> Dict[str, Any]:
    """KWタームプレミアムのキャッシュ状態を取得"""
    try:
        return fred_service.get_cache_status("THREEFYTP10")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/kw-term-premium/cache")
def invalidate_kw_cache() -> Dict[str, Any]:
    """KWタームプレミアムのキャッシュを無効化"""
    try:
        success = fred_service.invalidate_cache("THREEFYTP10")
        return {
            "success": success,
            "series_id": "THREEFYTP10",
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )


# =============================================================================
# CRE Loan Delinquency Rate Endpoints
# =============================================================================


@router.get("/cre-loan-delinquency")
def get_cre_loan_delinquency(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    CREローン延滞率データを取得

    Returns:
        - data: 延滞率データ（all_banks, top_100, other_banks）
        - latest: 最新データ
        - metadata: メタ情報
        - next_release: 次回発表予定

    Args:
        refresh: Trueの場合、キャッシュを無視して再取得
    """
    start_time = time.time()

    try:
        result = cre_loan_delinquency_service.get_cre_delinquency_data(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="CRE Loan Delinquency data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "data": result["data"],
            "latest": result.get("latest"),
            "metadata": result.get("metadata", {}),
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
            detail=f"Error fetching CRE Loan Delinquency: {str(e)}"
        )


@router.get("/cre-loan-delinquency/status")
def get_cre_loan_delinquency_status() -> Dict[str, Any]:
    """CREローン延滞率のキャッシュ状態を取得"""
    try:
        return cre_loan_delinquency_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/cre-loan-delinquency/cache")
def invalidate_cre_loan_delinquency_cache() -> Dict[str, Any]:
    """CREローン延滞率のキャッシュを無効化"""
    try:
        success = cre_loan_delinquency_service.invalidate_cache()
        return {
            "success": success,
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
