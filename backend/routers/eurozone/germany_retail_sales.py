"""
ドイツ小売売上高 APIエンドポイント

FMPデータベースからドイツ小売売上高データを取得するエンドポイント
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.eurozone.germany_retail_sales_service import germany_retail_sales_service


router = APIRouter(
    prefix="/api/eurozone",
    tags=["eurozone", "germany", "consumer"],
)


@router.get("/germany-retail-sales")
async def get_germany_retail_sales(
    force_refresh: bool = Query(False, description="Force refresh from database")
) -> Dict[str, Any]:
    """
    ドイツ小売売上高データを取得

    Returns:
        retail_sales_yoy: 小売売上高前年比データの時系列
        retail_sales_mom: 小売売上高前月比データの時系列
        metadata: データに関するメタ情報
        next_release: 次回発表日時
        cached: キャッシュからの取得かどうか
        source: データソース
    """
    return germany_retail_sales_service.get_germany_retail_sales_data(
        force_refresh=force_refresh
    )


@router.get("/germany-retail-sales/cache-status")
async def get_germany_retail_sales_cache_status() -> Dict[str, Any]:
    """
    ドイツ小売売上高キャッシュ状態を取得

    Returns:
        キャッシュの状態情報
    """
    return germany_retail_sales_service.get_cache_status()


@router.post("/germany-retail-sales/invalidate-cache")
async def invalidate_germany_retail_sales_cache() -> Dict[str, Any]:
    """
    ドイツ小売売上高キャッシュを無効化

    Returns:
        success: 無効化が成功したかどうか
    """
    success = germany_retail_sales_service.invalidate_cache()
    return {"success": success}
