"""
ドイツPPI APIエンドポイント

FMPデータベースからドイツ生産者物価指数データを取得するエンドポイント
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.eurozone.germany_ppi_service import germany_ppi_service


router = APIRouter(
    prefix="/api/eurozone",
    tags=["eurozone", "germany", "inflation"],
)


@router.get("/germany-ppi")
async def get_germany_ppi(
    force_refresh: bool = Query(False, description="Force refresh from database")
) -> Dict[str, Any]:
    """
    ドイツPPIデータを取得

    Returns:
        data: PPI前年比・前月比データの時系列
        metadata: データに関するメタ情報
        next_release: 次回発表日時
        cached: キャッシュからの取得かどうか
        source: データソース
    """
    return germany_ppi_service.get_germany_ppi_data(
        force_refresh=force_refresh
    )


@router.get("/germany-ppi/cache-status")
async def get_germany_ppi_cache_status() -> Dict[str, Any]:
    """
    ドイツPPIキャッシュ状態を取得

    Returns:
        キャッシュの状態情報
    """
    return germany_ppi_service.get_cache_status()


@router.post("/germany-ppi/invalidate-cache")
async def invalidate_germany_ppi_cache() -> Dict[str, Any]:
    """
    ドイツPPIキャッシュを無効化

    Returns:
        success: 無効化が成功したかどうか
    """
    success = germany_ppi_service.invalidate_cache()
    return {"success": success}
