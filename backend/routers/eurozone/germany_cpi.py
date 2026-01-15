"""
ドイツCPI/HICP APIエンドポイント

FMPデータベースからドイツCPI・HICPデータを取得するエンドポイント
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.eurozone.germany_cpi_service import germany_cpi_service


router = APIRouter(
    prefix="/api/eurozone",
    tags=["eurozone", "germany", "inflation"],
)


@router.get("/germany-cpi")
async def get_germany_cpi(
    force_refresh: bool = Query(False, description="Force refresh from database")
) -> Dict[str, Any]:
    """
    ドイツCPI/HICPデータを取得

    Returns:
        cpi_yoy: CPI前年比データの時系列
        cpi_mom: CPI前月比データの時系列
        hicp_yoy: HICP前年比データの時系列
        hicp_mom: HICP前月比データの時系列
        metadata: データに関するメタ情報
        next_release: 次回発表日時
        cached: キャッシュからの取得かどうか
        source: データソース
    """
    return germany_cpi_service.get_germany_cpi_data(
        force_refresh=force_refresh
    )


@router.get("/germany-cpi/cache-status")
async def get_germany_cpi_cache_status() -> Dict[str, Any]:
    """
    ドイツCPIキャッシュ状態を取得

    Returns:
        キャッシュの状態情報
    """
    return germany_cpi_service.get_cache_status()


@router.post("/germany-cpi/invalidate-cache")
async def invalidate_germany_cpi_cache() -> Dict[str, Any]:
    """
    ドイツCPIキャッシュを無効化

    Returns:
        success: 無効化が成功したかどうか
    """
    success = germany_cpi_service.invalidate_cache()
    return {"success": success}
