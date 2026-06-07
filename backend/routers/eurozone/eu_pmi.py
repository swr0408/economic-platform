"""
ユーロ圏 HCOB PMI APIルーター

エンドポイント:
- GET /api/eurozone/pmi - HCOB PMIデータを取得
- GET /api/eurozone/pmi/cache-status - キャッシュ状態を取得
- POST /api/eurozone/pmi/refresh - キャッシュを無効化して再取得
- DELETE /api/eurozone/pmi/cache - キャッシュを削除
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.eu_pmi_service import eu_pmi_service
except ImportError:
    from services.eurozone.eu_pmi_service import eu_pmi_service


router = APIRouter(
    prefix="/api/eurozone/pmi",
    tags=["eurozone", "pmi"]
)


@router.get("")
def get_eu_pmi(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """
    ユーロ圏 HCOB PMIデータを取得（製造業、サービス業、総合）

    Args:
        refresh: キャッシュを無視して再取得するか

    Returns:
        HCOB PMIデータ（3系列）
    """
    result = eu_pmi_service.get_eu_pmi_data(force_refresh=refresh)

    if not result.get("manufacturing") and not result.get("services") and not result.get("composite"):
        if "error" in result:
            raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@router.get("/cache-status")
def get_cache_status():
    """
    キャッシュの状態を取得

    Returns:
        キャッシュ状態情報
    """
    return eu_pmi_service.get_cache_status()


@router.post("/refresh")
def refresh_data():
    """
    キャッシュを無効化してデータを再取得

    Returns:
        更新結果
    """
    eu_pmi_service.invalidate_cache()
    result = eu_pmi_service.get_eu_pmi_data(force_refresh=True)

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
def delete_cache():
    """
    キャッシュを削除

    Returns:
        削除結果
    """
    success = eu_pmi_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache deleted" if success else "Cache not found or already deleted"
    }
