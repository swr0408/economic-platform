"""
日本 S&P Global PMI API Router

エンドポイント:
- GET /api/japan/pmi - PMIデータ取得（製造業/サービス業/総合）
- GET /api/japan/pmi/cache-status - キャッシュステータス取得
- POST /api/japan/pmi/refresh - データ強制更新
- DELETE /api/japan/pmi/cache - キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.japan.jp_pmi_service import jp_pmi_service
except ImportError:
    from services.japan.jp_pmi_service import jp_pmi_service

router = APIRouter(prefix="/api/japan/pmi", tags=["Japan - S&P Global PMI"])


@router.get("")
async def get_jp_pmi_data(
    force_refresh: bool = Query(False, description="Force refresh from source")
):
    """
    日本 S&P Global PMIデータを取得

    Args:
        force_refresh: キャッシュを無視して強制更新

    Returns:
        PMIデータ（製造業/サービス業/総合）
    """
    try:
        result = jp_pmi_service.get_jp_pmi_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-status")
async def get_cache_status():
    """
    キャッシュステータスを取得

    Returns:
        キャッシュの状態情報
    """
    try:
        return jp_pmi_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_data():
    """
    データを強制更新

    Returns:
        更新後のデータ
    """
    try:
        result = jp_pmi_service.get_jp_pmi_data(force_refresh=True)
        mfg_count = len(result.get("manufacturing", {}).get("data", [])) if result.get("manufacturing") else 0
        svc_count = len(result.get("services", {}).get("data", [])) if result.get("services") else 0
        cmp_count = len(result.get("composite", {}).get("data", [])) if result.get("composite") else 0
        return {
            "status": "refreshed",
            "data_count": {
                "manufacturing": mfg_count,
                "services": svc_count,
                "composite": cmp_count,
            },
            "last_updated": result.get("last_updated")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
async def invalidate_cache():
    """
    キャッシュを削除

    Returns:
        削除結果
    """
    try:
        success = jp_pmi_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
