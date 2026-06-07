"""
GDPデフレーター ルーター

エンドポイント:
- /api/japan/gdp-deflator: GDPデフレーター（前年同期比）データ
- /api/japan/gdp-deflator/cache-status: キャッシュ状態確認
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.japan.gdp_deflator_service import gdp_deflator_service

router = APIRouter(prefix="/api/japan", tags=["Japan GDP Deflator"])


@router.get("/gdp-deflator")
def get_gdp_deflator_data(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得")
) -> Dict[str, Any]:
    """
    GDPデフレーター（前年同期比）データを取得

    Args:
        force_refresh: キャッシュを無視して再取得

    Returns:
        GDPデフレーターデータ
    """
    return gdp_deflator_service.get_gdp_deflator_data(force_refresh=force_refresh)


@router.get("/gdp-deflator/cache-status")
def get_gdp_deflator_cache_status() -> Dict[str, Any]:
    """
    GDPデフレーターのキャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return gdp_deflator_service.get_cache_status()
