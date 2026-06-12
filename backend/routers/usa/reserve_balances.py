"""
準備預金残高（FRED WRBWFRBL/WRESBAL）APIルーター
週次データ（毎週水曜日発表）
"""
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

try:
    from backend.services.usa.reserve_balances_service import reserve_balances_service
except ImportError:
    from services.usa.reserve_balances_service import reserve_balances_service

router = APIRouter(prefix="/api/usa/frb", tags=["frb"])


@router.get("/reserve-balances")
def get_reserve_balances(
    refresh: bool = Query(False, description="強制的にキャッシュを更新する")
) -> Dict[str, Any]:
    """
    準備預金残高（WRBWFRBL/WRESBAL）を取得

    Reserve Balances with Federal Reserve Banks
    - WRBWFRBL: 週平均
    - WRESBAL: 週末時点
    週次データ（毎週水曜日 3:30 PM ET発表）
    """
    start_time = time.time()

    try:
        # リファクタ後のサービスは単一シリーズ (WRBWFRBL) の
        # {data, latest, next_release, ...} 形を返す。
        # 旧 wrbwfrbl/wresbal 二系列形を期待していた本ルーターは常時 404 だった。
        result = reserve_balances_service.get_data(force_refresh=refresh)

        if not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="Reserve Balances data not available"
            )

        response_time_ms = (time.time() - start_time) * 1000

        return {
            "series_id": reserve_balances_service.SERIES_ID,
            "data": result.get("data", []),
            "latest": result.get("latest"),
            "next_release": result.get("next_release"),
            "meta": {
                "cached": result.get("cached", False),
                "source": result.get("source", "unknown"),
                "last_updated": result.get("last_updated"),
                "response_time_ms": round(response_time_ms, 2),
                "count": len(result.get("data", [])),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching Reserve Balances: {str(e)}"
        )


@router.get("/reserve-balances/status")
def get_reserve_balances_cache_status() -> Dict[str, Any]:
    """準備預金残高のキャッシュ状態を取得"""
    try:
        return reserve_balances_service.get_cache_status()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache status: {str(e)}"
        )


@router.delete("/reserve-balances/cache")
def invalidate_reserve_balances_cache() -> Dict[str, Any]:
    """準備預金残高のキャッシュを無効化"""
    try:
        success = reserve_balances_service.invalidate_cache()
        return {
            "success": success,
            "series_ids": ["WRBWFRBL", "WRESBAL"],
            "message": "Cache invalidated" if success else "Cache invalidation failed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating cache: {str(e)}"
        )
