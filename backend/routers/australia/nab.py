"""
NAB (National Australia Bank) 関連 APIルーター

エンドポイント:
- GET /api/australia/nab/cost-price - NABコスト・価格チャート画像URL一覧
- GET /api/australia/nab/cost-price/cost_growth - Chart 18 画像
- GET /api/australia/nab/cost-price/output_price_growth - Chart 20 画像
- POST /api/australia/nab/cost-price/refresh - 強制再抽出
- GET /api/australia/nab/cost-price/cache - キャッシュ状態
- DELETE /api/australia/nab/cost-price/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from typing import Dict, Any

from services.australia.nab_business_survey_cost_price_service import (
    nab_business_survey_cost_price_service,
)

router = APIRouter(
    prefix="/api/australia/nab",
    tags=["australia", "inflation"]
)


@router.get("/cost-price")
async def get_nab_cost_price(
    force_refresh: bool = Query(False, description="PDFから画像を強制再抽出"),
) -> Dict[str, Any]:
    """
    NAB企業調査 コスト・価格チャート画像のURL一覧を取得

    2枚のチャート:
    - cost_growth: Chart 18 (Purchase Costs + Labour Costs)
    - output_price_growth: Chart 20 (Product Price + Retail Price)
    """
    if force_refresh:
        nab_business_survey_cost_price_service.invalidate_cache()
        nab_business_survey_cost_price_service.check_and_extract()

    return nab_business_survey_cost_price_service.get_screenshot_urls()


@router.get("/cost-price/cost_growth")
async def get_cost_growth_image():
    """Chart 18: Cost Growth 画像を取得"""
    path = nab_business_survey_cost_price_service.get_screenshot_path("cost_growth")
    if path and path.exists():
        return FileResponse(path, media_type="image/png", filename="nab_chart18_cost_growth.png")
    # 自動抽出を試みる
    nab_business_survey_cost_price_service.check_and_extract()
    path = nab_business_survey_cost_price_service.get_screenshot_path("cost_growth")
    if path and path.exists():
        return FileResponse(path, media_type="image/png", filename="nab_chart18_cost_growth.png")
    return {"error": "Chart image not available"}


@router.get("/cost-price/output_price_growth")
async def get_output_price_growth_image():
    """Chart 20: Output Price Growth 画像を取得"""
    path = nab_business_survey_cost_price_service.get_screenshot_path("output_price_growth")
    if path and path.exists():
        return FileResponse(path, media_type="image/png", filename="nab_chart20_output_price_growth.png")
    # 自動抽出を試みる
    nab_business_survey_cost_price_service.check_and_extract()
    path = nab_business_survey_cost_price_service.get_screenshot_path("output_price_growth")
    if path and path.exists():
        return FileResponse(path, media_type="image/png", filename="nab_chart20_output_price_growth.png")
    return {"error": "Chart image not available"}


@router.post("/cost-price/refresh")
async def refresh_nab_charts():
    """PDFから画像を強制再抽出"""
    nab_business_survey_cost_price_service.invalidate_cache()
    success = nab_business_survey_cost_price_service.check_and_extract()
    return {
        "success": success,
        "data": nab_business_survey_cost_price_service.get_screenshot_urls(),
    }


@router.get("/cost-price/cache")
async def get_nab_cost_price_cache_status() -> Dict[str, Any]:
    """NABコスト・価格チャートのキャッシュ状態を取得"""
    return nab_business_survey_cost_price_service.get_cache_status()


@router.delete("/cost-price/cache")
async def invalidate_nab_cost_price_cache() -> Dict[str, Any]:
    """NABコスト・価格チャートのキャッシュを無効化"""
    result = nab_business_survey_cost_price_service.invalidate_cache()
    return {"success": result, "message": "Cache invalidated"}
