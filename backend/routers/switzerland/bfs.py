"""
BFS（スイス連邦統計局）関連 APIルーター

提供データ:
- Unemployment Rate（失業率）
"""
from fastapi import APIRouter, Query

router = APIRouter(
    prefix="/api/switzerland/bfs",
    tags=["switzerland", "employment"]
)


@router.get("/")
async def bfs_root():
    """BFS APIルート"""
    return {
        "message": "BFS (Federal Statistical Office) API",
        "status": "Active",
        "available_endpoints": [
            "/unemployment-rate - Unemployment Rate"
        ]
    }


@router.get("/unemployment-rate")
async def get_unemployment_rate(
    force_refresh: bool = Query(False, description="強制的にキャッシュを更新")
):
    """
    スイス失業率データを取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...}
        }
    """
    from services.switzerland.ch_unemployment_rate_service import ch_unemployment_rate_service

    return ch_unemployment_rate_service.get_unemployment_rate_data(force_refresh=force_refresh)


@router.get("/unemployment-rate/latest")
async def get_unemployment_rate_latest():
    """
    スイス失業率 最新データを取得

    Returns:
        最新のスイス失業率データ
    """
    from services.switzerland.ch_unemployment_rate_service import ch_unemployment_rate_service

    result = ch_unemployment_rate_service.get_unemployment_rate_data()
    return {
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
    }


@router.get("/unemployment-rate/cache/status")
async def get_unemployment_rate_cache_status():
    """スイス失業率 キャッシュ状態を取得"""
    from services.switzerland.ch_unemployment_rate_service import ch_unemployment_rate_service

    return ch_unemployment_rate_service.get_cache_status()


@router.delete("/unemployment-rate/cache")
async def invalidate_unemployment_rate_cache():
    """スイス失業率 キャッシュを無効化"""
    from services.switzerland.ch_unemployment_rate_service import ch_unemployment_rate_service

    success = ch_unemployment_rate_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
