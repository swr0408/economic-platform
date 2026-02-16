"""
オーストラリア準備銀行（RBA）関連 APIルーター

エンドポイント:
- GET /api/australia/rba/rate - RBA政策金利データ
- GET /api/australia/rba/rate/cache - キャッシュ状態
- DELETE /api/australia/rba/rate/cache - キャッシュ無効化
- GET /api/australia/rba/rate-tracker - ASX RBA Rate Trackerデータ
- GET /api/australia/rba/rate-tracker/cache - キャッシュ状態
- DELETE /api/australia/rba/rate-tracker/cache - キャッシュ無効化
- GET /api/australia/rba/smp-forecast - SMP経済予測データ
- GET /api/australia/rba/smp-forecast/cache - キャッシュ状態
- DELETE /api/australia/rba/smp-forecast/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.australia.rba_policy_rate_service import rba_policy_rate_service
from services.australia.asx_rate_tracker_service import asx_rate_tracker_service
from services.australia.rba_smp_forecast_service import rba_smp_forecast_service

router = APIRouter(
    prefix="/api/australia/rba",
    tags=["australia", "monetary_policy"]
)


@router.get("/rate")
async def get_rba_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    RBA政策金利（Cash Rate Target）データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return rba_policy_rate_service.get_au_rba_rate_data(force_refresh=force_refresh)


@router.get("/rate/cache")
async def get_rba_rate_cache_status() -> Dict[str, Any]:
    """
    RBA政策金利のキャッシュ状態を取得
    """
    return rba_policy_rate_service.get_cache_status()


@router.delete("/rate/cache")
async def invalidate_rba_rate_cache() -> Dict[str, bool]:
    """
    RBA政策金利のキャッシュを無効化
    """
    success = rba_policy_rate_service.invalidate_cache()
    return {"success": success}


# ===== ASX RBA Rate Tracker =====

@router.get("/rate-tracker")
async def get_asx_rate_tracker(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ASX RBA Rate Trackerデータを取得

    30日物銀行間キャッシュレート先物から算出された
    次回RBA会合での金利変更確率とインプライドイールドカーブ
    """
    return asx_rate_tracker_service.get_rate_tracker_data(force_refresh=force_refresh)


@router.get("/rate-tracker/cache")
async def get_asx_rate_tracker_cache_status() -> Dict[str, Any]:
    """
    ASX Rate Trackerのキャッシュ状態を取得
    """
    return asx_rate_tracker_service.get_cache_status()


@router.delete("/rate-tracker/cache")
async def invalidate_asx_rate_tracker_cache() -> Dict[str, bool]:
    """
    ASX Rate Trackerのキャッシュを無効化
    """
    success = asx_rate_tracker_service.invalidate_cache()
    return {"success": success}


# ===== RBA SMP Forecast =====

@router.get("/smp-forecast")
async def get_smp_forecast(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    RBA SMP (Statement on Monetary Policy) 経済予測データを取得

    7指標の最新・前回予測を比較形式で返却:
    政策金利, GDP, 世帯消費, 雇用, 失業率, CPI, CPI(トリム平均)
    """
    return rba_smp_forecast_service.get_smp_forecast_data(force_refresh=force_refresh)


@router.get("/smp-forecast/cache")
async def get_smp_forecast_cache_status() -> Dict[str, Any]:
    """SMP予測のキャッシュ状態を取得"""
    return rba_smp_forecast_service.get_cache_status()


@router.delete("/smp-forecast/cache")
async def invalidate_smp_forecast_cache() -> Dict[str, bool]:
    """SMP予測のキャッシュを無効化"""
    success = rba_smp_forecast_service.invalidate_cache()
    return {"success": success}
