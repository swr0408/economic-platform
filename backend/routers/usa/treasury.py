"""
Treasury API ルーター
- Federal Budget Balance (MTS)
- CBO Budget Projections
"""
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

try:
    from backend.services.usa.federal_budget_service import federal_budget_service
    from backend.services.usa.cbo_projections_service import cbo_projections_service
except ImportError:
    from services.usa.federal_budget_service import federal_budget_service
    from services.usa.cbo_projections_service import cbo_projections_service

router = APIRouter(prefix="/api/treasury", tags=["treasury"])


# =============================================================================
# Federal Budget Balance (MTS) Endpoints
# =============================================================================


@router.get("/federal-budget")
def get_federal_budget(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    連邦財政収支（MTS）データを取得

    Returns:
        - data: 時系列データ（歳入・歳出・財政収支）
        - latest: 最新値
        - metadata: メタ情報
        - next_release: 次回発表日

    Args:
        refresh: Trueの場合、キャッシュを無視して再取得
    """
    start_time = time.time()

    try:
        result = federal_budget_service.get_federal_budget_data(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="Federal Budget data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        # 次回発表日を取得
        next_release = federal_budget_service.get_next_release_date()

        return {
            "data": result["data"],
            "latest": result.get("latest"),
            "metadata": result.get("metadata", {}),
            "next_release": next_release,
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
            detail=f"Error fetching Federal Budget: {str(e)}"
        )


@router.get("/federal-budget/status")
def get_federal_budget_cache_status() -> Dict[str, Any]:
    """
    Federal Budget キャッシュの状態を取得
    """
    try:
        return federal_budget_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/federal-budget/cache")
def invalidate_federal_budget_cache() -> Dict[str, Any]:
    """
    Federal Budget キャッシュを無効化（削除）
    """
    try:
        success = federal_budget_service.invalidate_cache()
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
# CBO Budget Projections Endpoints
# =============================================================================


@router.get("/cbo-projections")
def get_cbo_projections(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    CBO財政見通しデータを取得

    Returns:
        - data: 見通しデータ（債務・赤字・歳入・歳出）
        - latest_baseline_date: 最新ベースライン日
        - projection_years: 見通し対象年度リスト
        - metadata: メタ情報

    Args:
        refresh: Trueの場合、キャッシュを無視して再取得
    """
    start_time = time.time()

    try:
        result = cbo_projections_service.get_cbo_projections_data(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="CBO projections data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "data": result["data"],
            "latest_baseline_date": result.get("latest_baseline_date"),
            "projection_years": result.get("projection_years", []),
            "metadata": result.get("metadata", {}),
            "meta": {
                "cached": result.get("cached", False),
                "source": result.get("source", "unknown"),
                "last_updated": result.get("last_updated"),
                "response_time_ms": round(response_time_ms, 2)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching CBO projections: {str(e)}"
        )


@router.get("/cbo-projections/status")
def get_cbo_projections_cache_status() -> Dict[str, Any]:
    """
    CBO Projections キャッシュの状態を取得
    """
    try:
        return cbo_projections_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/cbo-projections/cache")
def invalidate_cbo_projections_cache() -> Dict[str, Any]:
    """
    CBO Projections キャッシュを無効化（削除）
    """
    try:
        success = cbo_projections_service.invalidate_cache()
        return {
            "success": success,
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
