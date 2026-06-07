"""
Melbourne Institute 関連 APIルーター

エンドポイント:
- GET /api/australia/melbourne-institute/inflation-expectations - インフレ期待
- GET /api/australia/melbourne-institute/inflation-expectations/cache - キャッシュ状態
- DELETE /api/australia/melbourne-institute/inflation-expectations/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.australia.au_inflation_expectations_service import au_inflation_expectations_service

router = APIRouter(
    prefix="/api/australia/melbourne-institute",
    tags=["australia", "inflation"]
)


@router.get("/inflation-expectations")
def get_inflation_expectations(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    Melbourne Institute インフレ期待データを取得

    1系列:
    - Consumer Inflation Expectations (%)
    """
    return au_inflation_expectations_service.get_au_inflation_expectations_data(
        force_refresh=force_refresh
    )


@router.get("/inflation-expectations/cache")
def get_inflation_expectations_cache_status() -> Dict[str, Any]:
    """インフレ期待のキャッシュ状態を取得"""
    return au_inflation_expectations_service.get_cache_status()


@router.delete("/inflation-expectations/cache")
def invalidate_inflation_expectations_cache() -> Dict[str, bool]:
    """インフレ期待のキャッシュを無効化"""
    success = au_inflation_expectations_service.invalidate_cache()
    return {"success": success}
