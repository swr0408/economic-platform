"""
スイス国立銀行（SNB）関連 APIルーター

エンドポイント:
- GET /api/switzerland/snb/rate - SNB政策金利データ
- GET /api/switzerland/snb/rate/cache - キャッシュ状態
- DELETE /api/switzerland/snb/rate/cache - キャッシュ無効化
- GET /api/switzerland/snb/inflation-forecast - インフレ見通しデータ
- GET /api/switzerland/snb/inflation-forecast/image/{filename} - インフレ見通し画像
- GET /api/switzerland/snb/inflation-forecast/cache - キャッシュ状態
- DELETE /api/switzerland/snb/inflation-forecast/cache - キャッシュ無効化
- GET /api/switzerland/snb/balance-sheet - SNBバランスシートデータ
- GET /api/switzerland/snb/balance-sheet/cache - キャッシュ状態
- DELETE /api/switzerland/snb/balance-sheet/cache - キャッシュ無効化
- GET /api/switzerland/snb/sight-deposits - SNB当座預金データ
- GET /api/switzerland/snb/sight-deposits/cache - キャッシュ状態
- DELETE /api/switzerland/snb/sight-deposits/cache - キャッシュ無効化
- GET /api/switzerland/snb/foreign-currency-reserves - 外貨準備データ
- GET /api/switzerland/snb/foreign-currency-reserves/cache - キャッシュ状態
- DELETE /api/switzerland/snb/foreign-currency-reserves/cache - キャッシュ無効化
- GET /api/switzerland/snb/monetary-base - マネタリーベースデータ
- GET /api/switzerland/snb/monetary-base/cache - キャッシュ状態
- DELETE /api/switzerland/snb/monetary-base/cache - キャッシュ無効化
- GET /api/switzerland/snb/monetary-aggregate-m2 - 貨幣総量M2データ
- GET /api/switzerland/snb/monetary-aggregate-m2/cache - キャッシュ状態
- DELETE /api/switzerland/snb/monetary-aggregate-m2/cache - キャッシュ無効化
- GET /api/switzerland/snb/mortgage-rates - 住宅ローン金利データ
- GET /api/switzerland/snb/mortgage-rates/cache - キャッシュ状態
- DELETE /api/switzerland/snb/mortgage-rates/cache - キャッシュ無効化
- GET /api/switzerland/snb/mortgage-balance - 住宅ローン残高データ
- GET /api/switzerland/snb/mortgage-balance/cache - キャッシュ状態
- DELETE /api/switzerland/snb/mortgage-balance/cache - キャッシュ無効化
- GET /api/switzerland/snb/new-mortgage-loans - 新規住宅ローン融資額データ
- GET /api/switzerland/snb/new-mortgage-loans/cache - キャッシュ状態
- DELETE /api/switzerland/snb/new-mortgage-loans/cache - キャッシュ無効化
"""
from fastapi import APIRouter, Query, Response
from typing import Dict, Any

from services.switzerland.ch_snb_rate_service import ch_snb_rate_service
from services.switzerland.ch_inflation_forecast_service import ch_inflation_forecast_service
from services.switzerland.snb_balance_sheet_service import snb_balance_sheet_service
from services.switzerland.snb_sight_deposits_service import snb_sight_deposits_service
from services.switzerland.foreign_currency_reserves_service import foreign_currency_reserves_service
from services.switzerland.monetary_base_service import monetary_base_service
from services.switzerland.monetary_aggregate_m2_service import monetary_aggregate_m2_service
from services.switzerland.ch_mortgage_rates_service import ch_mortgage_rates_service
from services.switzerland.ch_mortgage_balance_service import ch_mortgage_balance_service
from services.switzerland.ch_new_mortgage_loans_service import ch_new_mortgage_loans_service
from services.switzerland.ch_balance_of_trade_service import ch_balance_of_trade_service
from services.switzerland.ch_current_account_service import ch_current_account_service
from services.switzerland.ch_current_account_gdp_ratio_service import ch_current_account_gdp_ratio_service

router = APIRouter(
    prefix="/api/switzerland/snb",
    tags=["switzerland", "monetary_policy"]
)


@router.get("/rate")
async def get_snb_rate(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    SNB政策金利データを取得

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
    return ch_snb_rate_service.get_ch_snb_rate_data(force_refresh=force_refresh)


@router.get("/rate/cache")
async def get_snb_rate_cache_status() -> Dict[str, Any]:
    """
    SNB政策金利のキャッシュ状態を取得
    """
    return ch_snb_rate_service.get_cache_status()


@router.delete("/rate/cache")
async def invalidate_snb_rate_cache() -> Dict[str, bool]:
    """
    SNB政策金利のキャッシュを無効化
    """
    success = ch_snb_rate_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# インフレ見通し
# =============================================================================

@router.get("/inflation-forecast")
async def get_inflation_forecast(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    SNBインフレ見通しデータを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "releases": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ch_inflation_forecast_service.get_inflation_forecast_data(force_refresh=force_refresh)


@router.get("/inflation-forecast/image/{filename}")
async def get_inflation_forecast_image(filename: str):
    """
    SNBインフレ見通し画像を取得

    Args:
        filename: 画像ファイル名（例: 20251211_observed.png）

    Returns:
        PNG画像
    """
    image_data = ch_inflation_forecast_service.get_image(filename)
    if image_data:
        return Response(content=image_data, media_type="image/png")
    return Response(content=b"", status_code=404)


@router.get("/inflation-forecast/cache")
async def get_inflation_forecast_cache_status() -> Dict[str, Any]:
    """
    SNBインフレ見通しのキャッシュ状態を取得
    """
    return ch_inflation_forecast_service.get_cache_status()


@router.delete("/inflation-forecast/cache")
async def invalidate_inflation_forecast_cache() -> Dict[str, bool]:
    """
    SNBインフレ見通しのキャッシュを無効化
    """
    success = ch_inflation_forecast_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# バランスシート
# =============================================================================

@router.get("/balance-sheet")
async def get_balance_sheet(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    SNBバランスシート（総資産）データを取得

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
    return snb_balance_sheet_service.get_balance_sheet_data(force_refresh=force_refresh)


@router.get("/balance-sheet/cache")
async def get_balance_sheet_cache_status() -> Dict[str, Any]:
    """
    SNBバランスシートのキャッシュ状態を取得
    """
    return snb_balance_sheet_service.get_cache_status()


@router.delete("/balance-sheet/cache")
async def invalidate_balance_sheet_cache() -> Dict[str, bool]:
    """
    SNBバランスシートのキャッシュを無効化
    """
    success = snb_balance_sheet_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 当座預金
# =============================================================================

@router.get("/sight-deposits")
async def get_sight_deposits(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    SNB当座預金データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "last_publishing_date": str,
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return snb_sight_deposits_service.get_sight_deposits_data(force_refresh=force_refresh)


@router.get("/sight-deposits/cache")
async def get_sight_deposits_cache_status() -> Dict[str, Any]:
    """
    SNB当座預金のキャッシュ状態を取得
    """
    return snb_sight_deposits_service.get_cache_status()


@router.delete("/sight-deposits/cache")
async def invalidate_sight_deposits_cache() -> Dict[str, bool]:
    """
    SNB当座預金のキャッシュを無効化
    """
    success = snb_sight_deposits_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 外貨準備
# =============================================================================

@router.get("/foreign-currency-reserves")
async def get_foreign_currency_reserves(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    外貨準備データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "last_publishing_date": str,
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return foreign_currency_reserves_service.get_foreign_currency_reserves_data(force_refresh=force_refresh)


@router.get("/foreign-currency-reserves/cache")
async def get_foreign_currency_reserves_cache_status() -> Dict[str, Any]:
    """
    外貨準備のキャッシュ状態を取得
    """
    return foreign_currency_reserves_service.get_cache_status()


@router.delete("/foreign-currency-reserves/cache")
async def invalidate_foreign_currency_reserves_cache() -> Dict[str, bool]:
    """
    外貨準備のキャッシュを無効化
    """
    success = foreign_currency_reserves_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# マネタリーベース
# =============================================================================

@router.get("/monetary-base")
async def get_monetary_base(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    マネタリーベースデータを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": str,
            "last_publishing_date": str,
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return monetary_base_service.get_monetary_base_data(force_refresh=force_refresh)


@router.get("/monetary-base/cache")
async def get_monetary_base_cache_status() -> Dict[str, Any]:
    """
    マネタリーベースのキャッシュ状態を取得
    """
    return monetary_base_service.get_cache_status()


@router.delete("/monetary-base/cache")
async def invalidate_monetary_base_cache() -> Dict[str, bool]:
    """
    マネタリーベースのキャッシュを無効化
    """
    success = monetary_base_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 貨幣総量M2
# =============================================================================

@router.get("/monetary-aggregate-m2")
async def get_monetary_aggregate_m2(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    貨幣総量M2データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": str,
            "last_publishing_date": str,
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return monetary_aggregate_m2_service.get_monetary_aggregate_m2_data(force_refresh=force_refresh)


@router.get("/monetary-aggregate-m2/cache")
async def get_monetary_aggregate_m2_cache_status() -> Dict[str, Any]:
    """
    貨幣総量M2のキャッシュ状態を取得
    """
    return monetary_aggregate_m2_service.get_cache_status()


@router.delete("/monetary-aggregate-m2/cache")
async def invalidate_monetary_aggregate_m2_cache() -> Dict[str, bool]:
    """
    貨幣総量M2のキャッシュを無効化
    """
    success = monetary_aggregate_m2_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 住宅ローン金利
# =============================================================================

@router.get("/mortgage-rates")
async def get_mortgage_rates(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    住宅ローン金利（新規契約）データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": str,
            "last_publishing_date": str,
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ch_mortgage_rates_service.get_mortgage_rates_data(force_refresh=force_refresh)


@router.get("/mortgage-rates/cache")
async def get_mortgage_rates_cache_status() -> Dict[str, Any]:
    """
    住宅ローン金利のキャッシュ状態を取得
    """
    return ch_mortgage_rates_service.get_cache_status()


@router.delete("/mortgage-rates/cache")
async def invalidate_mortgage_rates_cache() -> Dict[str, bool]:
    """
    住宅ローン金利のキャッシュを無効化
    """
    success = ch_mortgage_rates_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 住宅ローン残高
# =============================================================================

@router.get("/mortgage-balance")
async def get_mortgage_balance(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    住宅ローン残高（国内・CHF建て・全銀行）データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": str,
            "last_publishing_date": str,
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ch_mortgage_balance_service.get_mortgage_balance_data(force_refresh=force_refresh)


@router.get("/mortgage-balance/cache")
async def get_mortgage_balance_cache_status() -> Dict[str, Any]:
    """
    住宅ローン残高のキャッシュ状態を取得
    """
    return ch_mortgage_balance_service.get_cache_status()


@router.delete("/mortgage-balance/cache")
async def invalidate_mortgage_balance_cache() -> Dict[str, bool]:
    """
    住宅ローン残高のキャッシュを無効化
    """
    success = ch_mortgage_balance_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 新規住宅ローン融資額
# =============================================================================

@router.get("/new-mortgage-loans")
async def get_new_mortgage_loans(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    新規住宅ローン融資額（四半期）データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得

    Returns:
        {
            "data": [...],
            "latest": {...},
            "metadata": {...},
            "next_release": str,
            "last_publishing_date": str,
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    return ch_new_mortgage_loans_service.get_new_mortgage_loans_data(force_refresh=force_refresh)


@router.get("/new-mortgage-loans/cache")
async def get_new_mortgage_loans_cache_status() -> Dict[str, Any]:
    """
    新規住宅ローン融資額のキャッシュ状態を取得
    """
    return ch_new_mortgage_loans_service.get_cache_status()


@router.delete("/new-mortgage-loans/cache")
async def invalidate_new_mortgage_loans_cache() -> Dict[str, bool]:
    """
    新規住宅ローン融資額のキャッシュを無効化
    """
    success = ch_new_mortgage_loans_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 貿易収支
# =============================================================================

@router.get("/balance-of-trade")
async def get_balance_of_trade(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    貿易収支データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得
    """
    return ch_balance_of_trade_service.get_data(force_refresh=force_refresh)


@router.get("/balance-of-trade/cache")
async def get_balance_of_trade_cache_status() -> Dict[str, Any]:
    """
    貿易収支のキャッシュ状態を取得
    """
    return ch_balance_of_trade_service.get_cache_status()


@router.delete("/balance-of-trade/cache")
async def invalidate_balance_of_trade_cache() -> Dict[str, bool]:
    """
    貿易収支のキャッシュを無効化
    """
    success = ch_balance_of_trade_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 経常収支
# =============================================================================

@router.get("/current-account")
async def get_current_account(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    経常収支データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得
    """
    return ch_current_account_service.get_data(force_refresh=force_refresh)


@router.get("/current-account/cache")
async def get_current_account_cache_status() -> Dict[str, Any]:
    """
    経常収支のキャッシュ状態を取得
    """
    return ch_current_account_service.get_cache_status()


@router.delete("/current-account/cache")
async def invalidate_current_account_cache() -> Dict[str, bool]:
    """
    経常収支のキャッシュを無効化
    """
    success = ch_current_account_service.invalidate_cache()
    return {"success": success}


# =============================================================================
# 経常収支対GDP比
# =============================================================================

@router.get("/current-account-gdp-ratio")
async def get_current_account_gdp_ratio(
    force_refresh: bool = Query(False, description="強制的にデータを再取得")
) -> Dict[str, Any]:
    """
    経常収支対GDP比データを取得

    Args:
        force_refresh: Trueの場合、キャッシュを無視して再取得
    """
    return ch_current_account_gdp_ratio_service.get_data(force_refresh=force_refresh)


@router.get("/current-account-gdp-ratio/cache")
async def get_current_account_gdp_ratio_cache_status() -> Dict[str, Any]:
    """
    経常収支対GDP比のキャッシュ状態を取得
    """
    return ch_current_account_gdp_ratio_service.get_cache_status()


@router.delete("/current-account-gdp-ratio/cache")
async def invalidate_current_account_gdp_ratio_cache() -> Dict[str, bool]:
    """
    経常収支対GDP比のキャッシュを無効化
    """
    success = ch_current_account_gdp_ratio_service.invalidate_cache()
    return {"success": success}
