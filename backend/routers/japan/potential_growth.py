"""
潜在成長率 ルーター

エンドポイント:
- /api/japan/potential-growth: 潜在成長率データ
- /api/japan/potential-growth/cache-status: キャッシュ状態確認
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.japan.potential_growth_service import potential_growth_service

router = APIRouter(prefix="/api/japan", tags=["Japan Potential Growth"])


@router.get("/potential-growth")
def get_potential_growth_data(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得")
) -> Dict[str, Any]:
    """
    潜在成長率データを取得

    Args:
        force_refresh: キャッシュを無視して再取得

    Returns:
        潜在成長率データ
    """
    return potential_growth_service.get_potential_growth_data(force_refresh=force_refresh)


@router.get("/potential-growth/cache-status")
def get_potential_growth_cache_status() -> Dict[str, Any]:
    """
    潜在成長率のキャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return potential_growth_service.get_cache_status()
