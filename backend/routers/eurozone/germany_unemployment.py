"""
ドイツ失業率APIエンドポイント

Deutsche Bundesbank APIからドイツ失業率データを取得するエンドポイント
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.eurozone.germany_unemployment_service import germany_unemployment_service


router = APIRouter(
    prefix="/api/eurozone",
    tags=["eurozone", "germany", "employment"],
)


@router.get("/germany-unemployment")
async def get_germany_unemployment(
    force_refresh: bool = Query(False, description="Force refresh from API")
) -> Dict[str, Any]:
    """
    ドイツ失業率データを取得

    Returns:
        unemployment_rate: 失業率データの時系列
        metadata: データに関するメタ情報
        next_release: 次回発表日時
        cached: キャッシュからの取得かどうか
        source: データソース
    """
    return germany_unemployment_service.get_germany_unemployment_data(
        force_refresh=force_refresh
    )


@router.get("/germany-unemployment/cache-status")
async def get_germany_unemployment_cache_status() -> Dict[str, Any]:
    """
    ドイツ失業率キャッシュ状態を取得

    Returns:
        キャッシュの状態情報
    """
    return germany_unemployment_service.get_cache_status()


@router.post("/germany-unemployment/invalidate-cache")
async def invalidate_germany_unemployment_cache() -> Dict[str, Any]:
    """
    ドイツ失業率キャッシュを無効化

    Returns:
        success: 無効化が成功したかどうか
    """
    success = germany_unemployment_service.invalidate_cache()
    return {"success": success}
