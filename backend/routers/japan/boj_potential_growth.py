"""
日銀潜在成長率 ルーター

エンドポイント:
- /api/japan/boj-potential-growth: 日銀潜在成長率データ
- /api/japan/boj-potential-growth/cache-status: キャッシュ状態確認
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.japan.boj_potential_growth_service import boj_potential_growth_service

router = APIRouter(prefix="/api/japan", tags=["Japan BOJ Potential Growth"])


@router.get("/boj-potential-growth")
async def get_boj_potential_growth_data(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得")
) -> Dict[str, Any]:
    """
    日銀潜在成長率データを取得

    Args:
        force_refresh: キャッシュを無視して再取得

    Returns:
        日銀潜在成長率データ
    """
    return boj_potential_growth_service.get_boj_potential_growth_data(force_refresh=force_refresh)


@router.get("/boj-potential-growth/cache-status")
async def get_boj_potential_growth_cache_status() -> Dict[str, Any]:
    """
    日銀潜在成長率のキャッシュ状態を取得

    Returns:
        キャッシュ状態情報
    """
    return boj_potential_growth_service.get_cache_status()
