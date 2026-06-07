"""
オーストラリア消費関連 APIルーター

エンドポイント:
- GET /api/australia/abs/household-spending - 家計支出データ
- GET /api/australia/abs/household-spending/cache - キャッシュ状態
- DELETE /api/australia/abs/household-spending/cache - キャッシュ無効化
- GET /api/australia/abs/westpac-consumer-confidence - Westpac消費者信頼感指数データ
- GET /api/australia/abs/westpac-consumer-confidence/cache - キャッシュ状態
- DELETE /api/australia/abs/westpac-consumer-confidence/cache - キャッシュ無効化
- GET /api/australia/abs/nab-business-confidence - NAB企業信頼感指数データ
- GET /api/australia/abs/nab-business-confidence/cache - キャッシュ状態
- DELETE /api/australia/abs/nab-business-confidence/cache - キャッシュ無効化
- GET /api/australia/abs/consumer-spending - 個人消費データ
- GET /api/australia/abs/consumer-spending/cache - キャッシュ状態
- DELETE /api/australia/abs/consumer-spending/cache - キャッシュ無効化
- GET /api/australia/abs/household-saving-ratio - 家計貯蓄率データ
- GET /api/australia/abs/household-saving-ratio/cache - キャッシュ状態
- DELETE /api/australia/abs/household-saving-ratio/cache - キャッシュ無効化
- GET /api/australia/abs/disposable-personal-income - 可処分所得データ
- GET /api/australia/abs/disposable-personal-income/cache - キャッシュ状態
- DELETE /api/australia/abs/disposable-personal-income/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.australia.au_household_spending_service import au_household_spending_service
from services.australia.au_westpac_consumer_confidence_service import au_westpac_consumer_confidence_service
from services.australia.au_nab_business_confidence_service import au_nab_business_confidence_service
from services.australia.au_consumer_spending_service import au_consumer_spending_service
from services.australia.au_household_saving_ratio_service import au_household_saving_ratio_service
from services.australia.au_disposable_personal_income_service import au_disposable_personal_income_service

router = APIRouter(
    prefix="/api/australia/abs",
    tags=["australia", "consumer"]
)


@router.get("/household-spending")
def get_household_spending(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    ABS 家計支出データを取得

    2系列:
    - MoM (%) - 前月比
    - YoY (%) - 前年比
    """
    return au_household_spending_service.get_au_household_spending_data(force_refresh=force_refresh)


@router.get("/household-spending/cache")
def get_household_spending_cache_status() -> Dict[str, Any]:
    """家計支出のキャッシュ状態を取得"""
    return au_household_spending_service.get_cache_status()


@router.delete("/household-spending/cache")
def invalidate_household_spending_cache() -> Dict[str, bool]:
    """家計支出のキャッシュを無効化"""
    success = au_household_spending_service.invalidate_cache()
    return {"success": success}


@router.get("/westpac-consumer-confidence")
def get_westpac_consumer_confidence(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    Westpac消費者信頼感指数データを取得

    2系列:
    - value: 指数
    - change: 前月比 (%)
    """
    return au_westpac_consumer_confidence_service.get_au_westpac_consumer_confidence_data(force_refresh=force_refresh)


@router.get("/westpac-consumer-confidence/cache")
def get_westpac_consumer_confidence_cache_status() -> Dict[str, Any]:
    """Westpac消費者信頼感指数のキャッシュ状態を取得"""
    return au_westpac_consumer_confidence_service.get_cache_status()


@router.delete("/westpac-consumer-confidence/cache")
def invalidate_westpac_consumer_confidence_cache() -> Dict[str, bool]:
    """Westpac消費者信頼感指数のキャッシュを無効化"""
    success = au_westpac_consumer_confidence_service.invalidate_cache()
    return {"success": success}


@router.get("/nab-business-confidence")
def get_nab_business_confidence(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    NAB企業信頼感指数データを取得

    2系列:
    - value: 指数
    - mom: 前月比（ポイント差分）
    """
    return au_nab_business_confidence_service.get_au_nab_business_confidence_data(force_refresh=force_refresh)


@router.get("/nab-business-confidence/cache")
def get_nab_business_confidence_cache_status() -> Dict[str, Any]:
    """NAB企業信頼感指数のキャッシュ状態を取得"""
    return au_nab_business_confidence_service.get_cache_status()


@router.delete("/nab-business-confidence/cache")
def invalidate_nab_business_confidence_cache() -> Dict[str, bool]:
    """NAB企業信頼感指数のキャッシュを無効化"""
    success = au_nab_business_confidence_service.invalidate_cache()
    return {"success": success}


@router.get("/consumer-spending")
def get_consumer_spending(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    個人消費データを取得（ABS Modellers' Database）

    2系列:
    - qoq: 前期比 (%)
    - yoy: 前年比 (%)
    """
    return au_consumer_spending_service.get_au_consumer_spending_data(force_refresh=force_refresh)


@router.get("/consumer-spending/cache")
def get_consumer_spending_cache_status() -> Dict[str, Any]:
    """個人消費のキャッシュ状態を取得"""
    return au_consumer_spending_service.get_cache_status()


@router.delete("/consumer-spending/cache")
def invalidate_consumer_spending_cache() -> Dict[str, bool]:
    """個人消費のキャッシュを無効化"""
    success = au_consumer_spending_service.invalidate_cache()
    return {"success": success}


@router.get("/household-saving-ratio")
def get_household_saving_ratio(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    家計貯蓄率データを取得（ABS National Accounts Key Aggregates）

    3系列:
    - value: 貯蓄率 (%)
    - qoq: 前期比変化幅 (pt)
    - yoy: 前年比変化幅 (pt)
    """
    return au_household_saving_ratio_service.get_au_household_saving_ratio_data(force_refresh=force_refresh)


@router.get("/household-saving-ratio/cache")
def get_household_saving_ratio_cache_status() -> Dict[str, Any]:
    """家計貯蓄率のキャッシュ状態を取得"""
    return au_household_saving_ratio_service.get_cache_status()


@router.delete("/household-saving-ratio/cache")
def invalidate_household_saving_ratio_cache() -> Dict[str, bool]:
    """家計貯蓄率のキャッシュを無効化"""
    success = au_household_saving_ratio_service.invalidate_cache()
    return {"success": success}


@router.get("/disposable-personal-income")
def get_disposable_personal_income(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    可処分所得データを取得（ABS 5206.0 Table 20）

    2系列:
    - qoq: 前期比 (%)
    - yoy: 前年比 (%)
    """
    return au_disposable_personal_income_service.get_au_disposable_personal_income_data(force_refresh=force_refresh)


@router.get("/disposable-personal-income/cache")
def get_disposable_personal_income_cache_status() -> Dict[str, Any]:
    """可処分所得のキャッシュ状態を取得"""
    return au_disposable_personal_income_service.get_cache_status()


@router.delete("/disposable-personal-income/cache")
def invalidate_disposable_personal_income_cache() -> Dict[str, bool]:
    """可処分所得のキャッシュを無効化"""
    success = au_disposable_personal_income_service.invalidate_cache()
    return {"success": success}
