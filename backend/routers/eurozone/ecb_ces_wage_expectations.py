"""
ECB CES賃金期待APIルーター

エンドポイント:
- GET /api/eurozone/ecb-ces-wage-expectations - ECB CES賃金期待データを取得
- GET /api/eurozone/ecb-ces-wage-expectations/cache/status - キャッシュ状態を取得
- POST /api/eurozone/ecb-ces-wage-expectations/cache/invalidate - キャッシュを無効化
"""
from fastapi import APIRouter, HTTPException, Query

try:
    from backend.services.eurozone.ecb_ces_wage_expectations_service import ecb_ces_wage_expectations_service
except ImportError:
    from services.eurozone.ecb_ces_wage_expectations_service import ecb_ces_wage_expectations_service


router = APIRouter(
    prefix="/api/eurozone/ecb-ces-wage-expectations",
    tags=["eurozone", "ecb-ces-wage-expectations"]
)


@router.get("")
async def get_ecb_ces_wage_expectations(
    refresh: bool = Query(False, description="キャッシュを無視して再取得")
):
    """ECB CES賃金期待データを取得"""
    result = ecb_ces_wage_expectations_service.get_data(force_refresh=refresh)

    if not result.get("data") and "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return {
        "data": result["data"],
        "latest": result.get("latest"),
        "next_release": result.get("next_release"),
        "meta": {
            "cached": result.get("cached", False),
            "source": result.get("source"),
            "last_updated": result.get("last_updated"),
            "count": len(result.get("data", []))
        }
    }


@router.get("/cache/status")
async def get_cache_status():
    """キャッシュの状態を取得"""
    return ecb_ces_wage_expectations_service.get_cache_status()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """キャッシュを無効化"""
    success = ecb_ces_wage_expectations_service.invalidate_cache()
    return {
        "success": success,
        "message": "Cache invalidated" if success else "Failed to invalidate cache"
    }
