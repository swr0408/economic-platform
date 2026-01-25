"""
フランス HCOB PMI APIルーター

エンドポイント:
- GET /api/eurozone/france-pmi - HCOB PMIデータを取得
- GET /api/eurozone/france-pmi/cache-status - キャッシュ状態を取得
- POST /api/eurozone/france-pmi/refresh - キャッシュを無効化して再取得
- DELETE /api/eurozone/france-pmi/cache - キャッシュを削除
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.france_pmi_service import france_pmi_service
except ImportError:
    from services.eurozone.france_pmi_service import france_pmi_service


router = APIRouter(
    prefix="/api/eurozone/france-pmi",
    tags=["eurozone", "france", "pmi"]
)


@router.get("")
async def get_france_pmi(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    フランス HCOB PMIデータを取得（製造業、サービス業、総合）

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        HCOB PMIデータ（3系列）
    """
    result = france_pmi_service.get_france_pmi_data(force_refresh=refresh)

    if not result.get("manufacturing") and not result.get("services") and not result.get("composite"):
        if "error" in result:
            raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@router.get("/cache-status")
async def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return france_pmi_service.get_cache_status()


@router.post("/refresh")
async def refresh_data():
    """
    キャッシュを無効化してデータを再取得

    Returns:
        更新結果
    """
    france_pmi_service.invalidate_cache()
    result = france_pmi_service.get_france_pmi_data(force_refresh=True)

    return {
        "success": True,
        "message": "Data refreshed successfully",
        "data_count": {
            "manufacturing": len(result.get("manufacturing", {}).get("data", [])) if result.get("manufacturing") else 0,
            "services": len(result.get("services", {}).get("data", [])) if result.get("services") else 0,
            "composite": len(result.get("composite", {}).get("data", [])) if result.get("composite") else 0,
        }
    }


@router.delete("/cache")
async def delete_cache():
    """
    キャッシュを削除

    Returns:
        削除結果
    """
    success = france_pmi_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache deleted" if success else "Cache not found or already deleted"
    }
