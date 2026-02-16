"""
カナダ中央銀行（BOC）関連 APIルーター

エンドポイント:
- GET /api/canada/boc/rate - BOC政策金利データ
- GET /api/canada/boc/rate/cache - キャッシュ状態
- DELETE /api/canada/boc/rate/cache - キャッシュ無効化
- GET /api/canada/boc/mpr - BOC金融政策報告書データ
- GET /api/canada/boc/mpr/cache - MPRキャッシュ状態
- DELETE /api/canada/boc/mpr/cache - MPRキャッシュ無効化
- GET /api/canada/boc/balance-sheet - BOCバランスシートデータ
- GET /api/canada/boc/balance-sheet/cache - バランスシートキャッシュ状態
- DELETE /api/canada/boc/balance-sheet/cache - バランスシートキャッシュ無効化
- GET /api/canada/boc/banks-balance-sheet - カナダ銀行バランスシート（チャータード銀行）
- GET /api/canada/boc/banks-balance-sheet/cache - カナダ銀行バランスシートキャッシュ状態
- DELETE /api/canada/boc/banks-balance-sheet/cache - カナダ銀行バランスシートキャッシュ無効化
- GET /api/canada/boc/corra - CORRAデータ
- GET /api/canada/boc/corra/cache - CORRAキャッシュ状態
- DELETE /api/canada/boc/corra/cache - CORRAキャッシュ無効化
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from services.canada.ca_boc_rate_service import ca_boc_rate_service
from services.canada.boc_mpr_service import boc_mpr_service
from services.canada.boc_balance_sheet_service import boc_balance_sheet_service
from services.canada.canada_banks_balance_sheet_service import canada_banks_balance_sheet_service
from services.canada.ca_inflation_expectations_service import ca_inflation_expectations_service
from services.canada.ca_corra_service import ca_corra_service
from services.canada.ca_settlement_balances_service import ca_settlement_balances_service
from services.canada.ca_government_deposits_service import ca_government_deposits_service
from services.canada.ca_bos_service import ca_bos_service
from services.canada.ca_csce_service import ca_csce_service
from services.canada.ca_slos_service import ca_slos_service

router = APIRouter(
    prefix="/api/canada/boc",
    tags=["canada", "monetary_policy"]
)


@router.get("/rate")
async def get_boc_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    BOC政策金利データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_boc_rate_service.get_ca_boc_rate_data(force_refresh=force_refresh)


@router.get("/rate/cache")
async def get_boc_rate_cache_status() -> Dict[str, Any]:
    """
    BOC政策金利のキャッシュ状態を取得
    """
    return ca_boc_rate_service.get_cache_status()


@router.delete("/rate/cache")
async def invalidate_boc_rate_cache() -> Dict[str, bool]:
    """
    BOC政策金利のキャッシュを無効化
    """
    success = ca_boc_rate_service.invalidate_cache()
    return {"success": success}


# ===== BOC Monetary Policy Report (MPR) =====

@router.get("/mpr")
async def get_boc_mpr(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    BOC金融政策報告書（MPR）データを取得

    最新と前回の見通しデータを含む比較データを返す

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "latest_report": {...},
            "previous_report": {...},
            "comparison": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return boc_mpr_service.get_boc_mpr_data(force_refresh=force_refresh)


@router.get("/mpr/cache")
async def get_boc_mpr_cache_status() -> Dict[str, Any]:
    """
    BOC MPRのキャッシュ状態を取得
    """
    return boc_mpr_service.get_cache_status()


@router.delete("/mpr/cache")
async def invalidate_boc_mpr_cache() -> Dict[str, bool]:
    """
    BOC MPRのキャッシュを無効化
    """
    success = boc_mpr_service.invalidate_cache()
    return {"success": success}


# ===== BOC Balance Sheet =====

@router.get("/balance-sheet")
async def get_boc_balance_sheet(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    BOCバランスシート（総資産）データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return boc_balance_sheet_service.get_boc_balance_sheet_data(force_refresh=force_refresh)


@router.get("/balance-sheet/cache")
async def get_boc_balance_sheet_cache_status() -> Dict[str, Any]:
    """
    BOCバランスシートのキャッシュ状態を取得
    """
    return boc_balance_sheet_service.get_cache_status()


@router.delete("/balance-sheet/cache")
async def invalidate_boc_balance_sheet_cache() -> Dict[str, bool]:
    """
    BOCバランスシートのキャッシュを無効化
    """
    success = boc_balance_sheet_service.invalidate_cache()
    return {"success": success}


# ===== Canada Banks Balance Sheet (Chartered Banks) =====

@router.get("/banks-balance-sheet")
async def get_canada_banks_balance_sheet(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ銀行バランスシート（チャータード銀行・カナダドル資産合計）データを取得

    データソース: Statistics Canada Table 10-10-0109-01

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return canada_banks_balance_sheet_service.get_canada_banks_balance_sheet_data(force_refresh=force_refresh)


@router.get("/banks-balance-sheet/cache")
async def get_canada_banks_balance_sheet_cache_status() -> Dict[str, Any]:
    """
    カナダ銀行バランスシートのキャッシュ状態を取得
    """
    return canada_banks_balance_sheet_service.get_cache_status()


@router.delete("/banks-balance-sheet/cache")
async def invalidate_canada_banks_balance_sheet_cache() -> Dict[str, bool]:
    """
    カナダ銀行バランスシートのキャッシュを無効化
    """
    success = canada_banks_balance_sheet_service.invalidate_cache()
    return {"success": success}


# ===== Inflation Expectations (Consumer Survey) =====

@router.get("/inflation-expectations")
async def get_inflation_expectations(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダインフレ期待（消費者調査）データを取得

    データソース: Bank of Canada Consumer Expectations Survey
    - CES_C1_SHORT_TERM: 1年先インフレ期待
    - CES_C1_MID_TERM: 2年先インフレ期待
    - CES_C1_LONG_TERM: 5年先インフレ期待

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "exp_1y": float, "exp_2y": float, "exp_5y": float}, ...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_inflation_expectations_service.get_ca_inflation_expectations_data(force_refresh=force_refresh)


@router.get("/inflation-expectations/cache")
async def get_inflation_expectations_cache_status() -> Dict[str, Any]:
    """
    インフレ期待のキャッシュ状態を取得
    """
    return ca_inflation_expectations_service.get_cache_status()


@router.delete("/inflation-expectations/cache")
async def invalidate_inflation_expectations_cache() -> Dict[str, bool]:
    """
    インフレ期待のキャッシュを無効化
    """
    success = ca_inflation_expectations_service.invalidate_cache()
    return {"success": success}


# ===== CORRA (Canadian Overnight Repo Rate Average) =====

@router.get("/corra")
async def get_corra(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    CORRA（カナダ翌日物レポ平均金利）データを取得

    データソース: Bank of Canada Valet API

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_corra_service.get_ca_corra_data(force_refresh=force_refresh)


@router.get("/corra/cache")
async def get_corra_cache_status() -> Dict[str, Any]:
    """
    CORRAのキャッシュ状態を取得
    """
    return ca_corra_service.get_cache_status()


@router.delete("/corra/cache")
async def invalidate_corra_cache() -> Dict[str, bool]:
    """
    CORRAのキャッシュを無効化
    """
    success = ca_corra_service.invalidate_cache()
    return {"success": success}


# ===== Settlement Balances (Lynx) =====

@router.get("/settlement-balances")
async def get_settlement_balances(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ決済残高（Lynx Settlement Balances）データを取得

    データソース: Bank of Canada Valet API - V36636
    - Members of Payments Canada deposits (週次)
    - 短期資金市場の流動性指標

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float}, ...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_settlement_balances_service.get_ca_settlement_balances_data(force_refresh=force_refresh)


@router.get("/settlement-balances/cache")
async def get_settlement_balances_cache_status() -> Dict[str, Any]:
    """
    決済残高のキャッシュ状態を取得
    """
    return ca_settlement_balances_service.get_cache_status()


@router.delete("/settlement-balances/cache")
async def invalidate_settlement_balances_cache() -> Dict[str, bool]:
    """
    決済残高のキャッシュを無効化
    """
    success = ca_settlement_balances_service.invalidate_cache()
    return {"success": success}


# ===== Government Deposits (TGA相当) =====

@router.get("/government-deposits")
async def get_government_deposits(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ政府預金（Government of Canada Canadian dollar deposits）データを取得

    データソース: Bank of Canada Valet API
    - GOCCADDEPTOT: 政府預金合計
    - GOCCADDEPBOC: BOC保有分
    - GOCCADDEPAP: オークション参加者保有分

    TGA相当の指標。政府預金の増減＝民間資金の吸収/放出

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "value": float, "total": float, "boc": float, "ap": float}, ...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_government_deposits_service.get_ca_government_deposits_data(force_refresh=force_refresh)


@router.get("/government-deposits/cache")
async def get_government_deposits_cache_status() -> Dict[str, Any]:
    """
    政府預金のキャッシュ状態を取得
    """
    return ca_government_deposits_service.get_cache_status()


@router.delete("/government-deposits/cache")
async def invalidate_government_deposits_cache() -> Dict[str, bool]:
    """
    政府預金のキャッシュを無効化
    """
    success = ca_government_deposits_service.invalidate_cache()
    return {"success": success}


# ===== Business Outlook Survey (BOS) =====

@router.get("/bos")
async def get_bos(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ企業景況感調査（BOS）データを取得

    データソース: Bank of Canada Valet API - BOS Group
    - Future Sales Growth (Balance of Opinion)
    - Investment in M&E
    - Employment Intentions
    - Input/Output Price Inflation

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "future_sales": float, "investment": float, ...}, ...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_bos_service.get_ca_bos_data(force_refresh=force_refresh)


@router.get("/bos/cache")
async def get_bos_cache_status() -> Dict[str, Any]:
    """
    BOSのキャッシュ状態を取得
    """
    return ca_bos_service.get_cache_status()


@router.delete("/bos/cache")
async def invalidate_bos_cache() -> Dict[str, bool]:
    """
    BOSのキャッシュを無効化
    """
    success = ca_bos_service.invalidate_cache()
    return {"success": success}


# ===== Canadian Survey of Consumer Expectations (CSCE) =====

@router.get("/csce")
async def get_csce(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ消費者期待調査（CSCE）データを取得

    データソース: Bank of Canada Valet API - CSCE
    - 賃金成長期待・実績
    - 失業・退職・求職確率
    - 所得・支出成長期待
    - インフレ期待（1年・2年・5年先）

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "wage_next_12m": float, ...}, ...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_csce_service.get_ca_csce_data(force_refresh=force_refresh)


@router.get("/csce/cache")
async def get_csce_cache_status() -> Dict[str, Any]:
    """
    CSCEのキャッシュ状態を取得
    """
    return ca_csce_service.get_cache_status()


@router.delete("/csce/cache")
async def invalidate_csce_cache() -> Dict[str, bool]:
    """
    CSCEのキャッシュを無効化
    """
    success = ca_csce_service.invalidate_cache()
    return {"success": success}


# ===== Senior Loan Officer Survey (SLOS) =====

@router.get("/slos")
async def get_slos(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    カナダ貸出態度調査（SLOS）データを取得

    データソース: Bank of Canada Valet API - SLOS Group
    - Overall Business Lending Conditions
    - Overall Mortgage Lending Conditions
    - Overall Non-Mortgage Lending Conditions

    正(+)=厳格化, 負(-)=緩和

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "business": float, "mortgage": float, "non_mortgage": float}, ...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ca_slos_service.get_ca_slos_data(force_refresh=force_refresh)


@router.get("/slos/cache")
async def get_slos_cache_status() -> Dict[str, Any]:
    """
    SLOSのキャッシュ状態を取得
    """
    return ca_slos_service.get_cache_status()


@router.delete("/slos/cache")
async def invalidate_slos_cache() -> Dict[str, bool]:
    """
    SLOSのキャッシュを無効化
    """
    success = ca_slos_service.invalidate_cache()
    return {"success": success}
