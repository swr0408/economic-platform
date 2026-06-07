"""
Treasury Quarterly Refunding API Router

エンドポイント:
- GET  /api/usa/quarterly-refunding              — メインデータ取得
- GET  /api/usa/quarterly-refunding/cache-status  — キャッシュステータス
- POST /api/usa/quarterly-refunding/refresh       — データ強制更新（index page scrape）
- DELETE /api/usa/quarterly-refunding/cache        — キャッシュ削除
"""

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.usa.quarterly_refunding_service import quarterly_refunding_service
except ImportError:
    from services.usa.quarterly_refunding_service import quarterly_refunding_service

router = APIRouter(
    prefix="/api/usa/quarterly-refunding",
    tags=["USA - Quarterly Refunding"],
)


@router.get("")
def get_quarterly_refunding_data(
    force_refresh: bool = Query(False, description="Force refresh from Treasury website"),
):
    """四半期リファンディングデータを取得"""
    try:
        result = quarterly_refunding_service.get_data(force_refresh=force_refresh)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-status")
def get_cache_status():
    """キャッシュステータスを取得"""
    try:
        return quarterly_refunding_service.get_cache_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def refresh_data():
    """データを強制更新（index pageスクレイプ）"""
    try:
        result = quarterly_refunding_service.get_data(force_refresh=True)
        return {
            "status": "refreshed",
            "quarter_label": result.get("quarter_label"),
            "events_count": len(result.get("events", {})),
            "auction_count": len(result.get("auction_schedule", [])),
            "buyback_count": len(result.get("buyback_schedule", [])),
            "last_updated": result.get("last_updated"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
def invalidate_cache():
    """キャッシュを削除"""
    try:
        success = quarterly_refunding_service.invalidate_cache()
        return {
            "status": "success" if success else "no_cache",
            "message": "Cache invalidated" if success else "No cache to invalidate",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
