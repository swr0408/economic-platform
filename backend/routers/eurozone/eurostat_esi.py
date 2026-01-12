"""
Eurostat ESI (Economic Sentiment Indicator) APIルーター

エンドポイント:
- GET /api/eurozone/esi - ESIデータを取得
- GET /api/eurozone/esi/cache/status - キャッシュ状態を取得
- POST /api/eurozone/esi/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.eurostat_esi_service import eurostat_esi_service
except ImportError:
    from services.eurozone.eurostat_esi_service import eurostat_esi_service


router = APIRouter(
    prefix="/api/eurozone/esi",
    tags=["eurozone", "esi"]
)


@router.get("")
async def get_eurostat_esi(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    Eurostat ESIデータを取得

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        ESIデータ（ユーロ圏・ドイツ・フランス・イタリア）
    """
    result = eurostat_esi_service.get_eurostat_esi_data(force_refresh=refresh)

    if not result.get("euro_area") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "euro_area": result.get("euro_area", []),
        "germany": result.get("germany", []),
        "france": result.get("france", []),
        "italy": result.get("italy", []),
        "metadata": result.get("metadata", {}),
        "next_release": result.get("next_release"),
    }


@router.get("/cache/status")
async def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return eurostat_esi_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """
    キャッシュを無効化

    Returns:
        無効化結果
    """
    success = eurostat_esi_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
