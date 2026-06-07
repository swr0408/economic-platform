"""
BOE OIS Forward Curve API Router
BOE OISフォワードカーブ (1M-12M)

エンドポイント:
    GET /api/uk/boe-ois-curve          - OISカーブデータ
    GET /api/uk/boe-ois-curve/chart    - チャート表示用データ
"""
from fastapi import APIRouter, Query

from services.uk.boe_ois_curve_service import boe_ois_curve_service


router = APIRouter(
    prefix="/api/uk/boe-ois-curve",
    tags=["uk", "monetary_policy"]
)


@router.get("")
def get_ois_curve(
    force_refresh: bool = Query(False, description="強制更新")
):
    """
    BOE OISカーブデータを取得

    Returns:
        {
            "data": {
                "current": {"date": str, "data": {...}},
                "previous": {"date": str, "data": {...}},
                "metadata": {...}
            },
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return boe_ois_curve_service.get_ois_curve_data(force_refresh=force_refresh)


@router.get("/chart")
def get_ois_curve_chart():
    """
    チャート表示用のOISカーブデータを取得

    Returns:
        {
            "current": {"date": str, "data": {...}},
            "previous": {"date": str, "data": {...}},
            "metadata": {...}
        }
    """
    return boe_ois_curve_service.get_chart_data()


@router.get("/cache-status")
def get_cache_status():
    """キャッシュ状態を取得"""
    return boe_ois_curve_service.get_cache_status()


@router.post("/invalidate-cache")
def invalidate_cache():
    """キャッシュを無効化"""
    success = boe_ois_curve_service.invalidate_cache()
    return {"success": success}
