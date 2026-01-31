"""
KOF Swiss Economic Institute 関連 APIルーター

提供データ:
- KOF Economic Barometer（KOF経済バロメーター）
"""
from fastapi import APIRouter, Query

router = APIRouter(
    prefix="/api/switzerland/kof",
    tags=["switzerland", "consumer"]
)


@router.get("/")
async def kof_root():
    """KOF APIルート"""
    return {
        "message": "KOF Swiss Economic Institute API",
        "status": "Active",
        "available_endpoints": [
            "/barometer - KOF Economic Barometer"
        ]
    }


@router.get("/barometer")
async def get_kof_barometer(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    KOF経済バロメーターデータを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.kof_economic_barometer_service import kof_economic_barometer_service

    return kof_economic_barometer_service.get_kof_barometer_data(force_refresh=force_refresh)


@router.get("/barometer/latest")
async def get_kof_barometer_latest():
    """
    KOF経済バロメーター最新データを取得

    Returns:
        最新のKOF経済バロメーターデータ
    """
    from services.switzerland.kof_economic_barometer_service import kof_economic_barometer_service

    result = kof_economic_barometer_service.get_kof_barometer_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/barometer/cache/status")
async def get_kof_barometer_cache_status():
    """KOF経済バロメーター キャッシュ状態を取得"""
    from services.switzerland.kof_economic_barometer_service import kof_economic_barometer_service

    return kof_economic_barometer_service.get_cache_status()


@router.delete("/barometer/cache")
async def invalidate_kof_barometer_cache():
    """KOF経済バロメーター キャッシュを無効化"""
    from services.switzerland.kof_economic_barometer_service import kof_economic_barometer_service

    success = kof_economic_barometer_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
