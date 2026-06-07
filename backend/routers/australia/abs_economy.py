"""
オーストラリア経済関連 APIルーター

エンドポイント:
- GET /api/australia/abs/gdp-growth-rate - GDP成長率データ
- GET /api/australia/abs/gdp-growth-rate/cache - キャッシュ状態
- DELETE /api/australia/abs/gdp-growth-rate/cache - キャッシュ無効化
- GET /api/australia/abs/terms-of-trade - 交易条件
- GET /api/australia/abs/terms-of-trade/cache - キャッシュ状態
- DELETE /api/australia/abs/terms-of-trade/cache - キャッシュ無効化
- GET /api/australia/abs/pmi - S&P Global PMI
- GET /api/australia/abs/pmi/cache - キャッシュ状態
- DELETE /api/australia/abs/pmi/cache - キャッシュ無効化
- GET /api/australia/abs/gdp-price-related - GDP価格・支出関連データ
- GET /api/australia/abs/gdp-price-related/cache - キャッシュ状態
- DELETE /api/australia/abs/gdp-price-related/cache - キャッシュ無効化
- GET /api/australia/abs/private-capex - 民間新規設備投資データ
- GET /api/australia/abs/private-capex/cache - キャッシュ状態
- DELETE /api/australia/abs/private-capex/cache - キャッシュ無効化
- GET /api/australia/abs/international-trade - 国際貿易データ
- GET /api/australia/abs/international-trade/cache - キャッシュ状態
- DELETE /api/australia/abs/international-trade/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.australia.au_gdp_growth_rate_service import au_gdp_growth_rate_service
from services.australia.au_gdp_price_related_service import au_gdp_price_related_service
from services.australia.au_private_new_capital_expenditure_service import au_private_new_capital_expenditure_service
from services.australia.au_international_trade_service import au_international_trade_service
from services.australia.au_current_account_service import au_current_account_service
from services.australia.au_current_account_gdp_ratio_service import au_current_account_gdp_ratio_service
from services.australia.au_pmi_service import au_pmi_service
from services.australia.au_terms_of_trade_service import au_terms_of_trade_service

router = APIRouter(
    prefix="/api/australia/abs",
    tags=["australia", "economy"]
)


@router.get("/gdp-growth-rate")
def get_gdp_growth_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    GDP成長率データを取得（ABS 5206.0 Key Aggregates）

    2系列:
    - qoq: 前期比 (%)
    - yoy: 前年比 (%)
    """
    return au_gdp_growth_rate_service.get_au_gdp_growth_rate_data(force_refresh=force_refresh)


@router.get("/gdp-growth-rate/cache")
def get_gdp_growth_rate_cache_status() -> Dict[str, Any]:
    """GDP成長率のキャッシュ状態を取得"""
    return au_gdp_growth_rate_service.get_cache_status()


@router.delete("/gdp-growth-rate/cache")
def invalidate_gdp_growth_rate_cache() -> Dict[str, bool]:
    """GDP成長率のキャッシュを無効化"""
    success = au_gdp_growth_rate_service.invalidate_cache()
    return {"success": success}


@router.get("/gdp-price-related")
def get_gdp_price_related(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    GDP価格・支出関連データを取得（ABS 5206.0 Table 2 & 5）

    系列:
    - deflator_qoq: GDPデフレーター前期比 (%)
    - deflator_yoy: GDPデフレーター前年比 (%)
    - net_exports_contribution: 純輸出GDP寄与 (ppt)
    - exports_contribution: 輸出寄与 (ppt)
    - imports_contribution: 輸入寄与 (ppt)
    - gfcf_qoq: 設備投資(GFCF)前期比 (%)
    - gfcf_yoy: 設備投資(GFCF)前年比 (%)
    - gfcf_level: 設備投資(GFCF)レベル ($m)
    - consumption_qoq: 家計消費前期比 (%)
    - consumption_yoy: 家計消費前年比 (%)
    - consumption_level: 家計消費レベル ($m)
    """
    return au_gdp_price_related_service.get_au_gdp_price_related_data(force_refresh=force_refresh)


@router.get("/gdp-price-related/cache")
def get_gdp_price_related_cache_status() -> Dict[str, Any]:
    """GDP価格関連のキャッシュ状態を取得"""
    return au_gdp_price_related_service.get_cache_status()


@router.delete("/gdp-price-related/cache")
def invalidate_gdp_price_related_cache() -> Dict[str, bool]:
    """GDP価格関連のキャッシュを無効化"""
    success = au_gdp_price_related_service.invalidate_cache()
    return {"success": success}


@router.get("/private-capex")
def get_private_capex(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    民間新規設備投資データを取得（ABS 5625.0 CAPEX）

    3系列:
    - value: レベル値 ($m AUD, Chain Volume Measures, SA)
    - qoq: 前期比 (%)
    - yoy: 前年比 (%)
    """
    return au_private_new_capital_expenditure_service.get_au_private_new_capital_expenditure_data(force_refresh=force_refresh)


@router.get("/private-capex/cache")
def get_private_capex_cache_status() -> Dict[str, Any]:
    """民間新規設備投資のキャッシュ状態を取得"""
    return au_private_new_capital_expenditure_service.get_cache_status()


@router.delete("/private-capex/cache")
def invalidate_private_capex_cache() -> Dict[str, bool]:
    """民間新規設備投資のキャッシュを無効化"""
    success = au_private_new_capital_expenditure_service.invalidate_cache()
    return {"success": success}


# ===== 国際貿易 =====

@router.get("/international-trade")
def get_international_trade(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    国際貿易データを取得

    ABS SDMX API (ITGS dataflow):
    - Balance on goods (DATA_ITEM 170)
    - Goods Credit / Exports (DATA_ITEM 1000)
    - Goods Debit / Imports (DATA_ITEM 2000)
    - Seasonally Adjusted, Current Prices
    """
    return au_international_trade_service.get_au_international_trade_data(force_refresh=force_refresh)


@router.get("/international-trade/cache")
def get_international_trade_cache_status() -> Dict[str, Any]:
    """国際貿易のキャッシュ状態を取得"""
    return au_international_trade_service.get_cache_status()


@router.delete("/international-trade/cache")
def invalidate_international_trade_cache() -> Dict[str, bool]:
    """国際貿易のキャッシュを無効化"""
    success = au_international_trade_service.invalidate_cache()
    return {"success": success}


# ===== 経常収支 =====

@router.get("/current-account")
def get_current_account(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    経常収支データを取得

    ABS 5302.0 Table 4:
    - Series ID: A3535187L (Current account, Seasonally Adjusted)
    - 単位: B AUD (Billion AUD)
    """
    return au_current_account_service.get_au_current_account_data(force_refresh=force_refresh)


@router.get("/current-account/cache")
def get_current_account_cache_status() -> Dict[str, Any]:
    """経常収支のキャッシュ状態を取得"""
    return au_current_account_service.get_cache_status()


@router.delete("/current-account/cache")
def invalidate_current_account_cache() -> Dict[str, bool]:
    """経常収支のキャッシュを無効化"""
    success = au_current_account_service.invalidate_cache()
    return {"success": success}


# ===== 経常収支対GDP比 =====

@router.get("/current-account-gdp-ratio")
def get_current_account_gdp_ratio(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    経常収支対GDP比データを取得

    ABS 5302.0 (Current Account) / ABS 5206.0 (Nominal GDP)
    - Ratio (%) = (Current Account / Nominal GDP) × 100
    """
    return au_current_account_gdp_ratio_service.get_au_current_account_gdp_ratio_data(force_refresh=force_refresh)


@router.get("/current-account-gdp-ratio/cache")
def get_current_account_gdp_ratio_cache_status() -> Dict[str, Any]:
    """経常収支対GDP比のキャッシュ状態を取得"""
    return au_current_account_gdp_ratio_service.get_cache_status()


@router.delete("/current-account-gdp-ratio/cache")
def invalidate_current_account_gdp_ratio_cache() -> Dict[str, bool]:
    """経常収支対GDP比のキャッシュを無効化"""
    success = au_current_account_gdp_ratio_service.invalidate_cache()
    return {"success": success}


# ===== S&P Global PMI =====

@router.get("/pmi")
def get_pmi(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    S&P Global PMI データを取得

    3系列:
    - manufacturing: 製造業PMI
    - services: サービス業PMI
    - composite: 総合PMI
    """
    return au_pmi_service.get_au_pmi_data(force_refresh=force_refresh)


@router.get("/pmi/cache")
def get_pmi_cache_status() -> Dict[str, Any]:
    """PMIのキャッシュ状態を取得"""
    return au_pmi_service.get_cache_status()


@router.delete("/pmi/cache")
def invalidate_pmi_cache() -> Dict[str, bool]:
    """PMIのキャッシュを無効化"""
    success = au_pmi_service.invalidate_cache()
    return {"success": success}


# ===== 交易条件 =====

@router.get("/terms-of-trade")
def get_terms_of_trade(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    交易条件データを取得

    ABS 5206.0 Key Aggregates:
    - value: Index (Seasonally Adjusted)
    - qoq: 前期比 (%)
    - yoy: 前年比 (%, Index値から算出)
    """
    return au_terms_of_trade_service.get_au_terms_of_trade_data(force_refresh=force_refresh)


@router.get("/terms-of-trade/cache")
def get_terms_of_trade_cache_status() -> Dict[str, Any]:
    """交易条件のキャッシュ状態を取得"""
    return au_terms_of_trade_service.get_cache_status()


@router.delete("/terms-of-trade/cache")
def invalidate_terms_of_trade_cache() -> Dict[str, bool]:
    """交易条件のキャッシュを無効化"""
    success = au_terms_of_trade_service.invalidate_cache()
    return {"success": success}
