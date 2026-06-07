"""
APRA（Australian Prudential Regulation Authority）関連 APIルーター

エンドポイント:
- GET /api/australia/apra/housing-loan-arrears - 住宅ローン延滞率データ
- GET /api/australia/apra/housing-loan-arrears/cache - キャッシュ状態
- DELETE /api/australia/apra/housing-loan-arrears/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.australia.au_housing_loan_arrears_service import au_housing_loan_arrears_service

router = APIRouter(
    prefix="/api/australia/apra",
    tags=["australia", "apra"]
)


@router.get("/housing-loan-arrears")
def get_housing_loan_arrears(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    住宅ローン延滞率データを取得（APRA ADI Property Exposures）

    30-89日延滞率、不良債権率（90日以上）、合計延滞率
    """
    return au_housing_loan_arrears_service.get_au_housing_loan_arrears_data(force_refresh=force_refresh)


@router.get("/housing-loan-arrears/cache")
def get_housing_loan_arrears_cache_status() -> Dict[str, Any]:
    """住宅ローン延滞率のキャッシュ状態を取得"""
    return au_housing_loan_arrears_service.get_cache_status()


@router.delete("/housing-loan-arrears/cache")
def invalidate_housing_loan_arrears_cache() -> Dict[str, bool]:
    """住宅ローン延滞率のキャッシュを無効化"""
    success = au_housing_loan_arrears_service.invalidate_cache()
    return {"success": success}
