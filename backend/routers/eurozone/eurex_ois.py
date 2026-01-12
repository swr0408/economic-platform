"""
Eurex OIS Router
Eurex Three-Month Euro STR Futures OIS data endpoints
"""
from fastapi import APIRouter, Query

try:
    from backend.services.eurozone.eurex_ois_service import eurex_ois_service
except ImportError:
    from services.eurozone.eurex_ois_service import eurex_ois_service


router = APIRouter(
    prefix="/api/eurozone/eurex-ois",
    tags=["eurozone", "eurex-ois"]
)


@router.get("")
async def get_eurex_ois(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    Eurex Three-Month Euro STR Futures OISデータを取得

    Returns:
        Eurex OISカーブデータ（当日・前日比較用）
    """
    return eurex_ois_service.get_eurex_ois_data(force_refresh=refresh)


@router.get("/chart")
async def get_eurex_ois_chart(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    Eurex OISチャートデータを取得（フロントエンド用フォーマット）

    Returns:
        チャート用データ（ラベル、値、前日比較）
    """
    return eurex_ois_service.get_chart_data(force_refresh=refresh)


@router.post("/refresh")
async def refresh_eurex_ois():
    """
    Eurex OISデータを強制更新

    Returns:
        更新されたデータ
    """
    return eurex_ois_service.get_eurex_ois_data(force_refresh=True)


@router.get("/cache/status")
async def get_cache_status():
    """
    キャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return eurex_ois_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = eurex_ois_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
