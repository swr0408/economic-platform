"""
市場データAPI
yfinance を使用した銘柄データ取得エンドポイント

エンドポイント:
    GET /api/market/symbols           - 銘柄リスト取得
    GET /api/market/{symbol_id}/daily - 個別銘柄の日足データ取得
    GET /api/market/dashboard         - 全銘柄の最新データ（バッチ）
    GET /api/market/fear-greed        - CNN Fear & Greed Index
"""
import time
from typing import List, Optional
from fastapi import APIRouter, Path, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse

try:
    from backend.services.market.yfinance_service import yfinance_service
    from backend.services.market.symbols import (
        get_all_symbols,
        get_symbol_by_id,
        get_symbols_by_category,
        search_symbols,
        SYMBOL_CATEGORIES,
        SYMBOL_SUB_CATEGORIES,
    )
except ImportError:
    from services.market.yfinance_service import yfinance_service
    from services.market.symbols import (
        get_all_symbols,
        get_symbol_by_id,
        get_symbols_by_category,
        search_symbols,
        SYMBOL_CATEGORIES,
        SYMBOL_SUB_CATEGORIES,
    )

try:
    from backend.services.market.fear_greed_service import fear_greed_service
    from backend.services.market.naaim_service import naaim_service
    from backend.services.market.gex_dix_service import gex_dix_service
    from backend.services.market.cboe_pcr_service import cboe_pcr_service
    from backend.services.market.nikkei_regression_service import nikkei_regression_service
    from backend.services.market.electronic_components_balance_service import electronic_components_balance_service
    from backend.services.market.jpx_pcr_service import jpx_pcr_service
    from backend.services.market.nikkei_yoy_service import nikkei_yoy_service
    from backend.services.market.nikkei_double_inverse_service import nikkei_double_inverse_service
    from backend.services.market.jpx_investor_trading_service import jpx_investor_trading_service
    from backend.services.market.gold_etf_holdings_service import gold_etf_holdings_service
    from backend.services.market.wgc_gold_etf_service import wgc_gold_etf_service
    from backend.services.market.gold_premium_service import gold_premium_service
    from backend.services.market.sge_gold_service import sge_gold_service
    from backend.services.market.china_gold_etf_balance_service import china_gold_etf_balance_service
    from backend.services.market.lbma_stock_service import lbma_stock_service
    from backend.services.market.silver_etf_holdings_service import silver_etf_holdings_service
    from backend.services.market.weekly_crude_oil_inventories_service import weekly_crude_oil_inventories_service
    from backend.services.market.cushing_inventory_service import cushing_inventory_service
    from backend.services.market.us_gasoline_inventories_refinery_utilization_service import us_gasoline_inventories_refinery_utilization_service
    from backend.services.market.distillate_fuel_inventories_service import distillate_fuel_inventories_service
    from backend.services.market.api_weekly_crude_oil_inventories_service import api_weekly_crude_oil_inventories_service
    from backend.services.market.adjustments_service import adjustments_service
    from backend.services.market.us_shale_oil_production_service import us_shale_oil_production_service
    from backend.services.market.north_america_rig_count_service import north_america_rig_count_service
    from backend.services.market.crude_oil_net_demand_service import crude_oil_net_demand_service
    from backend.services.market.short_term_energy_outlook_service import short_term_energy_outlook_service
    from backend.services.market.us_natural_gas_storage_service import us_natural_gas_storage_service
    from backend.services.market.us_natural_gas_trade_service import us_natural_gas_trade_service
    from backend.services.market.lng_exports_by_region_service import lng_exports_by_region_service
    from backend.services.market.steo_natural_gas_service import steo_natural_gas_service
    from backend.services.market.opec_momr_service import opec_momr_service
    from backend.services.market.iea_oil_market_report_service import iea_oil_market_report_service
    from backend.services.market.eu_natural_gas_storage_service import eu_natural_gas_storage_service
    from backend.services.market.eu_natural_gas_production_service import eu_natural_gas_production_service
    from backend.services.market.noaa_hdd_cdd_service import noaa_hdd_cdd_service
    from backend.services.market.roni_service import roni_service
    from backend.services.market.lme_copper_stock_service import lme_copper_stock_service
    from backend.services.market.comex_gold_stock_service import comex_gold_stock_service
    from backend.services.market.comex_silver_stock_service import comex_silver_stock_service
    from backend.services.market.comex_copper_stock_service import comex_copper_stock_service
    from backend.services.market.shfe_copper_stock_service import shfe_copper_stock_service
    from backend.services.market.sp500_valuation_service import sp500_valuation_service
    from backend.services.market.nasdaq100_valuation_service import nasdaq100_valuation_service
    from backend.services.market.nikkei225_valuation_service import nikkei225_valuation_service
    from backend.services.market.topix_valuation_service import topix_valuation_service
    from backend.services.market.advance_decline_ratio_service import advance_decline_ratio_service
    from backend.services.market.cftc_positioning_service import cftc_positioning_service
    from backend.services.market.crack_spread_service import crack_spread_service
    from backend.services.market.vix_term_structure_service import vix_term_structure_service
    from backend.services.market.historical_volatility_service import historical_volatility_service
    from backend.services.market.vix_cross_ratio_service import vix_cross_ratio_service
    from backend.services.market.sector_ratio_service import sector_ratio_service
    from backend.services.market.copper_to_gold_ratio_service import copper_to_gold_ratio_service
    from backend.services.market.russell2000_russell1000_service import russell2000_russell1000_service
    from backend.services.market.financial_stress_index_service import financial_stress_index_service
    from backend.services.market.nt_magnification_service import nt_magnification_service
    from backend.services.market.us_interest_rate_spread_service import us_interest_rate_spread_service
    from backend.services.market.mof_securities_trading_service import mof_securities_trading_service
    from backend.services.market.nikkei225_options_service import nikkei225_options_service
    from backend.services.market.ny_option_cut_service import ny_option_cut_service
    from backend.services.market.cmdi_service import cmdi_service
except ImportError:
    from services.market.fear_greed_service import fear_greed_service
    from services.market.naaim_service import naaim_service
    from services.market.gex_dix_service import gex_dix_service
    from services.market.cboe_pcr_service import cboe_pcr_service
    from services.market.nikkei_regression_service import nikkei_regression_service
    from services.market.electronic_components_balance_service import electronic_components_balance_service
    from services.market.jpx_pcr_service import jpx_pcr_service
    from services.market.nikkei_yoy_service import nikkei_yoy_service
    from services.market.nikkei_double_inverse_service import nikkei_double_inverse_service
    from services.market.jpx_investor_trading_service import jpx_investor_trading_service
    from services.market.gold_etf_holdings_service import gold_etf_holdings_service
    from services.market.wgc_gold_etf_service import wgc_gold_etf_service
    from services.market.gold_premium_service import gold_premium_service
    from services.market.sge_gold_service import sge_gold_service
    from services.market.china_gold_etf_balance_service import china_gold_etf_balance_service
    from services.market.lbma_stock_service import lbma_stock_service
    from services.market.silver_etf_holdings_service import silver_etf_holdings_service
    from services.market.weekly_crude_oil_inventories_service import weekly_crude_oil_inventories_service
    from services.market.cushing_inventory_service import cushing_inventory_service
    from services.market.us_gasoline_inventories_refinery_utilization_service import us_gasoline_inventories_refinery_utilization_service
    from services.market.distillate_fuel_inventories_service import distillate_fuel_inventories_service
    from services.market.api_weekly_crude_oil_inventories_service import api_weekly_crude_oil_inventories_service
    from services.market.adjustments_service import adjustments_service
    from services.market.us_shale_oil_production_service import us_shale_oil_production_service
    from services.market.north_america_rig_count_service import north_america_rig_count_service
    from services.market.crude_oil_net_demand_service import crude_oil_net_demand_service
    from services.market.short_term_energy_outlook_service import short_term_energy_outlook_service
    from services.market.us_natural_gas_storage_service import us_natural_gas_storage_service
    from services.market.us_natural_gas_trade_service import us_natural_gas_trade_service
    from services.market.lng_exports_by_region_service import lng_exports_by_region_service
    from services.market.steo_natural_gas_service import steo_natural_gas_service
    from services.market.opec_momr_service import opec_momr_service
    from services.market.iea_oil_market_report_service import iea_oil_market_report_service
    from services.market.eu_natural_gas_storage_service import eu_natural_gas_storage_service
    from services.market.eu_natural_gas_production_service import eu_natural_gas_production_service
    from services.market.noaa_hdd_cdd_service import noaa_hdd_cdd_service
    from services.market.roni_service import roni_service
    from services.market.lme_copper_stock_service import lme_copper_stock_service
    from services.market.comex_gold_stock_service import comex_gold_stock_service
    from services.market.comex_silver_stock_service import comex_silver_stock_service
    from services.market.comex_copper_stock_service import comex_copper_stock_service
    from services.market.shfe_copper_stock_service import shfe_copper_stock_service
    from services.market.sp500_valuation_service import sp500_valuation_service
    from services.market.nasdaq100_valuation_service import nasdaq100_valuation_service
    from services.market.nikkei225_valuation_service import nikkei225_valuation_service
    from services.market.topix_valuation_service import topix_valuation_service
    from services.market.advance_decline_ratio_service import advance_decline_ratio_service
    from services.market.cftc_positioning_service import cftc_positioning_service
    from services.market.crack_spread_service import crack_spread_service
    from services.market.vix_term_structure_service import vix_term_structure_service
    from services.market.historical_volatility_service import historical_volatility_service
    from services.market.vix_cross_ratio_service import vix_cross_ratio_service
    from services.market.sector_ratio_service import sector_ratio_service
    from services.market.copper_to_gold_ratio_service import copper_to_gold_ratio_service
    from services.market.russell2000_russell1000_service import russell2000_russell1000_service
    from services.market.financial_stress_index_service import financial_stress_index_service
    from services.market.nt_magnification_service import nt_magnification_service
    from services.market.us_interest_rate_spread_service import us_interest_rate_spread_service
    from services.market.mof_securities_trading_service import mof_securities_trading_service
    from services.market.nikkei225_options_service import nikkei225_options_service
    from services.market.ny_option_cut_service import ny_option_cut_service
    from services.market.cmdi_service import cmdi_service


router = APIRouter(prefix="/api/market", tags=["Market"])


@router.get("/symbols")
async def get_symbols(
    category: Optional[str] = Query(None, description="カテゴリでフィルタ（forex, index, commodity, bond）"),
    search: Optional[str] = Query(None, description="検索クエリ"),
):
    """
    銘柄リストを取得

    Returns:
        {
            "symbols": [...],
            "categories": {...},
            "sub_categories": {...},
            "total": int
        }
    """
    if search:
        symbols = search_symbols(search)
    elif category:
        symbols = get_symbols_by_category(category)
    else:
        symbols = get_all_symbols()

    return {
        "symbols": symbols,
        "categories": SYMBOL_CATEGORIES,
        "sub_categories": SYMBOL_SUB_CATEGORIES,
        "total": len(symbols),
    }


@router.get("/dashboard")
def get_market_dashboard(
    symbols: Optional[str] = Query(None, description="カンマ区切りの銘柄IDリスト"),
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """
    市場データダッシュボード（バッチ取得）

    指定した銘柄の日足データをまとめて取得。
    symbols を省略すると全銘柄のデータを返す。

    Returns:
        {
            "data": {
                "usdjpy": {...},
                "sp500": {...},
                ...
            },
            "cached": bool,
            "response_time_ms": float
        }
    """
    start_time = time.time()

    if symbols:
        symbol_ids = [s.strip() for s in symbols.split(",")]
        result = yfinance_service.get_multiple_daily_data(symbol_ids, force_refresh)
    else:
        result = yfinance_service.get_all_symbols_data(force_refresh)

    # 全体のキャッシュ状態を判定
    all_cached = all(v.get("cached", False) for v in result.values() if v)

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "data": result,
            "cached": all_cached,
            "response_time_ms": round(response_time_ms, 2),
        },
        headers={
            "X-Cache": "HIT" if all_cached else "MISS",
            "X-Response-Time": f"{response_time_ms:.2f}ms",
        }
    )


@router.get("/fear-greed")
def get_fear_greed(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """
    CNN Fear & Greed Index データを取得

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "score": float, "rating": str, "sp500": float}, ...],
            "latest": {...},
            "metadata": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    start_time = time.time()
    result = fear_greed_service.get_fear_greed_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            **result,
            "response_time_ms": round(response_time_ms, 2),
        },
        headers={
            "X-Cache": "HIT" if result.get("cached") else "MISS",
            "X-Response-Time": f"{response_time_ms:.2f}ms",
        }
    )


@router.get("/naaim")
def get_naaim(force_refresh: bool = Query(False)):
    """NAAIM Exposure Index データを取得"""
    start_time = time.time()
    result = naaim_service.get_naaim_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/gex-dix")
def get_gex_dix(force_refresh: bool = Query(False)):
    """GEX / DIX データを取得"""
    start_time = time.time()
    result = gex_dix_service.get_gex_dix_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/cboe-pcr")
def get_cboe_pcr(force_refresh: bool = Query(False)):
    """CBOE Total Put/Call Ratio データを取得"""
    start_time = time.time()
    result = cboe_pcr_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/nikkei-regression")
def get_nikkei_regression(force_refresh: bool = Query(False)):
    """日経平均回帰モデル データを取得"""
    start_time = time.time()
    result = nikkei_regression_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/electronic-components-balance")
def get_electronic_components_balance(force_refresh: bool = Query(False)):
    """電子部品・デバイス工業 出荷在庫バランス データを取得"""
    start_time = time.time()
    result = electronic_components_balance_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/jpx-pcr")
def get_jpx_pcr(force_refresh: bool = Query(False)):
    """JPX 日本株指数オプション Put/Call Ratio データを取得"""
    start_time = time.time()
    result = jpx_pcr_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/nikkei-yoy")
def get_nikkei_yoy(force_refresh: bool = Query(False)):
    """日経平均 前年比 (YoY) データを取得"""
    start_time = time.time()
    result = nikkei_yoy_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/nikkei-double-inverse")
def get_nikkei_double_inverse(force_refresh: bool = Query(False)):
    """日経ダブルインバース (1357) 信用残データを取得"""
    start_time = time.time()
    result = nikkei_double_inverse_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/jpx-investor-trading")
def get_jpx_investor_trading(force_refresh: bool = Query(False)):
    """投資部門別売買状況データを取得"""
    start_time = time.time()
    result = jpx_investor_trading_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/gold-etf-holdings")
def get_gold_etf_holdings(force_refresh: bool = Query(False)):
    """金ETF保有残高データを取得"""
    start_time = time.time()
    result = gold_etf_holdings_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/wgc-gold-etf")
def get_wgc_gold_etf(
    data_type: str = Query("holdings_ton"),
    force_refresh: bool = Query(False),
):
    """WGC 金ETFフロー/保有残高データを取得"""
    start_time = time.time()
    result = wgc_gold_etf_service.get_data(data_type, force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/gold-premium")
def get_gold_premium(force_refresh: bool = Query(False)):
    """金プレミアム/ディスカウント（中国・インド）データを取得"""
    start_time = time.time()
    result = gold_premium_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/sge-gold")
def get_sge_gold(force_refresh: bool = Query(False)):
    """SGE Au(T+D) 日次取引データを取得"""
    start_time = time.time()
    result = sge_gold_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/china-gold-etf-balance")
def get_china_gold_etf_balance(force_refresh: bool = Query(False)):
    """中国金ETF残高（518880 華安黄金ETF）日次データを取得"""
    start_time = time.time()
    result = china_gold_etf_balance_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/lbma-stock")
def get_lbma_stock(force_refresh: bool = Query(False)):
    """LBMA London Vault Holdings 月次データを取得"""
    start_time = time.time()
    result = lbma_stock_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/silver-etf-holdings")
def get_silver_etf_holdings(force_refresh: bool = Query(False)):
    """銀ETF残高保有量（iShares Silver Trust）日次データを取得"""
    start_time = time.time()
    result = silver_etf_holdings_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/weekly-crude-oil-inventories")
def get_weekly_crude_oil_inventories(force_refresh: bool = Query(False)):
    """EIA 週間原油在庫データを取得"""
    start_time = time.time()
    result = weekly_crude_oil_inventories_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/cushing-inventory")
def get_cushing_inventory(force_refresh: bool = Query(False)):
    """EIA クッシング原油在庫データを取得"""
    start_time = time.time()
    result = cushing_inventory_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/gasoline-refinery")
def get_gasoline_refinery(force_refresh: bool = Query(False)):
    """EIA 米国ガソリン在庫 / 製油稼働率データを取得"""
    start_time = time.time()
    result = us_gasoline_inventories_refinery_utilization_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/api-weekly-crude-oil-inventories")
def get_api_weekly_crude_oil_inventories(force_refresh: bool = Query(False)):
    """API（米国石油協会）週間原油在庫データを取得"""
    start_time = time.time()
    result = api_weekly_crude_oil_inventories_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/adjustments")
def get_adjustments(force_refresh: bool = Query(False)):
    """EIA 商業在庫調整データを取得"""
    start_time = time.time()
    result = adjustments_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/shale-oil-production")
def get_shale_oil_production(force_refresh: bool = Query(False)):
    """米国シェールオイル生産量データを取得"""
    start_time = time.time()
    result = us_shale_oil_production_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/distillate-fuel-inventories")
def get_distillate_fuel_inventories(force_refresh: bool = Query(False)):
    """EIA 米国蒸留燃料在庫データを取得"""
    start_time = time.time()
    result = distillate_fuel_inventories_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/rig-count")
def get_rig_count(force_refresh: bool = Query(False)):
    """米石油採掘装置（リグ）稼働数データを取得"""
    start_time = time.time()
    result = north_america_rig_count_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/crude-oil-net-demand")
def get_crude_oil_net_demand(force_refresh: bool = Query(False)):
    """米国 原油純需要（STEO: 消費 - 生産）データを取得"""
    start_time = time.time()
    result = crude_oil_net_demand_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/short-term-energy-outlook")
def get_short_term_energy_outlook(force_refresh: bool = Query(False)):
    """EIA 短期エネルギー見通し（STEO）データを取得"""
    start_time = time.time()
    result = short_term_energy_outlook_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/steo-natural-gas")
def get_steo_natural_gas(force_refresh: bool = Query(False)):
    """EIA 短期エネルギー見通し（天然ガス）データを取得"""
    start_time = time.time()
    result = steo_natural_gas_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/opec-momr")
def get_opec_momr(force_refresh: bool = Query(False)):
    """OPEC MOMR (Monthly Oil Market Report) データを取得"""
    start_time = time.time()
    result = opec_momr_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/iea-oil-market-report")
def get_iea_oil_market_report(force_refresh: bool = Query(False)):
    """IEA Oil Market Report データを取得"""
    start_time = time.time()
    result = iea_oil_market_report_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/natural-gas-trade")
def get_natural_gas_trade(force_refresh: bool = Query(False)):
    """EIA 米国天然ガス輸出入データを取得"""
    start_time = time.time()
    result = us_natural_gas_trade_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/lng-exports-by-region")
def get_lng_exports_by_region(force_refresh: bool = Query(False)):
    """EIA 米国LNG輸出（国別・エリア別）データを取得"""
    start_time = time.time()
    result = lng_exports_by_region_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/natural-gas-storage")
def get_natural_gas_storage(force_refresh: bool = Query(False)):
    """EIA 米国天然ガス貯蔵量データを取得"""
    start_time = time.time()
    result = us_natural_gas_storage_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/eu-natural-gas-storage")
def get_eu_natural_gas_storage(force_refresh: bool = Query(False)):
    """EU天然ガス貯蔵量（AGSI+）データを取得"""
    start_time = time.time()
    result = eu_natural_gas_storage_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/eu-natural-gas-production")
def get_eu_natural_gas_production(force_refresh: bool = Query(False)):
    """EU天然ガス生産（Eurostat NRG_CB_GASM）データを取得"""
    start_time = time.time()
    result = eu_natural_gas_production_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/noaa-hdd-cdd")
def get_noaa_hdd_cdd(force_refresh: bool = Query(False)):
    """NOAA HDD/CDD & 気温見通しデータを取得"""
    start_time = time.time()
    result = noaa_hdd_cdd_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/roni")
def get_roni(force_refresh: bool = Query(False)):
    """RONI (Revised Oceanic Niño Index) データを取得"""
    start_time = time.time()
    result = roni_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/lme-copper-stock")
def get_lme_copper_stock(force_refresh: bool = Query(False)):
    """LME銅在庫データを取得"""
    start_time = time.time()
    result = lme_copper_stock_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/comex-gold-stock")
def get_comex_gold_stock(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """COMEX Gold Warehouse Stock データを取得"""
    result = comex_gold_stock_service.get_data(force_refresh=force_refresh)
    return JSONResponse(
        content=result,
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/comex-silver-stock")
def get_comex_silver_stock(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """COMEX銀在庫データを取得（日次、troy oz）"""
    import time as _time
    t0 = _time.time()
    data = comex_silver_stock_service.get_data(force_refresh=force_refresh)
    data["response_time_ms"] = round((_time.time() - t0) * 1000, 2)
    return data


@router.get("/comex-copper-stock")
def get_comex_copper_stock(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """COMEX Copper Warehouse Stock データを取得"""
    result = comex_copper_stock_service.get_data(force_refresh=force_refresh)
    return JSONResponse(
        content=result,
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/shfe-copper-stock")
def get_shfe_copper_stock(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """SHFE Copper Warehouse Stock データを取得"""
    result = shfe_copper_stock_service.get_data(force_refresh=force_refresh)
    return JSONResponse(
        content=result,
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/sp500-valuation")
def get_sp500_valuation(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """S&P 500 Valuation データ（予想PER/EPS/イールドスプレッド等）を取得"""
    start_time = time.time()
    result = sp500_valuation_service.get_data(force_refresh=force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/nasdaq100-valuation")
def get_nasdaq100_valuation(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """Nasdaq 100 Valuation データ（予想PER/EPS/イールドスプレッド等）を取得"""
    start_time = time.time()
    result = nasdaq100_valuation_service.get_data(force_refresh=force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/nikkei225-valuation")
def get_nikkei225_valuation(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """日経平均 Valuation データ（予想PER/EPS/イールドスプレッド等）を取得"""
    start_time = time.time()
    result = nikkei225_valuation_service.get_data(force_refresh=force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/topix-valuation")
def get_topix_valuation(
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """TOPIX Valuation データ（予想PER/EPS/イールドスプレッド等）を取得"""
    start_time = time.time()
    result = topix_valuation_service.get_data(force_refresh=force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/advance-decline-ratio")
def get_advance_decline_ratio(force_refresh: bool = Query(False)):
    """東証プライム 騰落レシオ（25日）データを取得"""
    start_time = time.time()
    result = advance_decline_ratio_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/nikkei225-options")
def get_nikkei225_options(force_refresh: bool = Query(False)):
    """日経225オプション データを取得（IV、建玉、出来高、清算値）"""
    start_time = time.time()
    result = nikkei225_options_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/ny-option-cut")
def get_ny_option_cut(force_refresh: bool = Query(False)):
    """NYオプションカット（FXオプション期日）データを取得"""
    start_time = time.time()
    result = ny_option_cut_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/ny-option-cut/table-image")
def get_ny_option_cut_table_image():
    """NYオプションカット テーブル画像を配信"""
    from pathlib import Path as _Path
    img_path = _Path(__file__).parent.parent / "data" / "cache" / "market" / "ny_option_cut_table.png"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Table image not found")
    return FileResponse(str(img_path), media_type="image/png")


@router.get("/{symbol_id}/daily")
def get_symbol_daily_data(
    symbol_id: str = Path(..., description="銘柄ID（例: usdjpy, sp500）"),
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """
    個別銘柄の日足データを取得

    Args:
        symbol_id: 銘柄ID

    Returns:
        {
            "data": [{"date": "YYYY-MM-DD", "open": float, "high": float, "low": float, "close": float}, ...],
            "latest": {"date": "YYYY-MM-DD", "close": float},
            "symbol": {...},
            "cached": bool,
            "source": str,
            "last_updated": str
        }
    """
    start_time = time.time()

    # 銘柄の存在確認
    symbol_info = get_symbol_by_id(symbol_id)
    if not symbol_info:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol_id}")

    result = yfinance_service.get_daily_data(symbol_id, force_refresh)

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            **result,
            "response_time_ms": round(response_time_ms, 2),
        },
        headers={
            "X-Cache": "HIT" if result.get("cached") else "MISS",
            "X-Response-Time": f"{response_time_ms:.2f}ms",
        }
    )


@router.get("/{symbol_id}/status")
def get_symbol_cache_status(
    symbol_id: str = Path(..., description="銘柄ID"),
):
    """
    銘柄のキャッシュ状態を取得

    Returns:
        {
            "symbol_id": str,
            "cache_key": str,
            "redis_exists": bool,
            "last_updated": str | null,
            "data_count": int,
            "file_cache_exists": bool
        }
    """
    symbol_info = get_symbol_by_id(symbol_id)
    if not symbol_info:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol_id}")

    return yfinance_service.get_cache_status(symbol_id)


@router.post("/{symbol_id}/refresh")
def refresh_symbol_cache(
    symbol_id: str = Path(..., description="銘柄ID"),
):
    """
    銘柄のキャッシュを強制更新

    Returns:
        {
            "success": bool,
            "message": str,
            "data_count": int
        }
    """
    symbol_info = get_symbol_by_id(symbol_id)
    if not symbol_info:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol_id}")

    # キャッシュを無効化
    yfinance_service.invalidate_cache(symbol_id)

    # 再取得
    result = yfinance_service.get_daily_data(symbol_id, force_refresh=True)

    return {
        "success": not result.get("error"),
        "message": f"Cache refreshed for {symbol_id}" if not result.get("error") else result.get("error"),
        "data_count": len(result.get("data", [])),
    }


@router.delete("/cache")
def invalidate_all_cache():
    """
    全銘柄のキャッシュを無効化

    Returns:
        {
            "success": bool,
            "invalidated_count": int
        }
    """
    count = yfinance_service.invalidate_all_cache()
    return {
        "success": True,
        "invalidated_count": count,
    }


# ===== CFTC Positioning =====


@router.get("/cftc-positioning")
def get_cftc_positioning(
    asset: str = Query(..., description="銘柄名 (gold, silver, sp500, usdjpy, etc.)"),
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """CFTC建玉報告ポジションデータ取得"""
    result = cftc_positioning_service.get_data(asset, force_refresh=force_refresh)
    return JSONResponse(
        content=result,
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/cftc-positioning/list")
def get_cftc_positioning_list():
    """CFTC建玉報告 利用可能銘柄一覧"""
    assets = cftc_positioning_service.get_available_assets()
    return JSONResponse(content={"assets": assets})


# ===== Crack Spread =====


@router.get("/crack-spread")
def get_crack_spread(force_refresh: bool = Query(False)):
    """クラックスプレッドデータを取得"""
    start_time = time.time()
    result = crack_spread_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/vix-term-structure")
def get_vix_term_structure(force_refresh: bool = Query(False)):
    """VIX期間構造（VIX9D / VIX / VIX3M）データを取得"""
    start_time = time.time()
    result = vix_term_structure_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/historical-volatility")
def get_historical_volatility(force_refresh: bool = Query(False)):
    """ヒストリカルボラティリティ（HV20/HV30）データを取得"""
    start_time = time.time()
    result = historical_volatility_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


@router.get("/vix-cross-ratio")
def get_vix_cross_ratio(force_refresh: bool = Query(False)):
    """VIXクロスレシオ（VVIX/VIX, MOVE/VIX, VXN/VIX, OVX/VIX, GVZ/VIX）データを取得"""
    start_time = time.time()
    result = vix_cross_ratio_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


# ===== Sector Ratio =====


@router.get("/sector-ratio")
def get_sector_ratio(force_refresh: bool = Query(False)):
    """セクターレシオ（XLY/XLP, XLF/XLU, HYG/LQD, HYG/IEF）データを取得"""
    start_time = time.time()
    result = sector_ratio_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


# ===== Copper-to-Gold Ratio =====


@router.get("/copper-to-gold-ratio")
def get_copper_to_gold_ratio(force_refresh: bool = Query(False)):
    """銅金レシオ（Copper/Gold × 1000）データを取得"""
    start_time = time.time()
    result = copper_to_gold_ratio_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


# ===== MOF Securities Trading =====


@router.get("/mof-securities-trading")
def get_mof_securities_trading(force_refresh: bool = Query(False)):
    """MOF対外対内証券売買データを取得"""
    start_time = time.time()
    result = mof_securities_trading_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


# ===== Russell 2000 / Russell 1000 Ratio =====


@router.get("/russell2000-russell1000")
def get_russell2000_russell1000(force_refresh: bool = Query(False)):
    """Russell 2000 / Russell 1000 レシオデータを取得"""
    start_time = time.time()
    result = russell2000_russell1000_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


# ===== Financial Stress Index (STLFSI4) =====


@router.get("/financial-stress-index")
def get_financial_stress_index(force_refresh: bool = Query(False)):
    """セントルイス連銀金融ストレス指数（STLFSI4）データを取得"""
    start_time = time.time()
    result = financial_stress_index_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


# ===== NT Magnification =====


@router.get("/nt-magnification")
def get_nt_magnification(force_refresh: bool = Query(False)):
    """NT倍率（日経平均/TOPIX）データを取得"""
    start_time = time.time()
    result = nt_magnification_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


# ===== US Interest Rate Spread =====


@router.get("/us-interest-rate-spread")
def get_us_interest_rate_spread(force_refresh: bool = Query(False)):
    """米国長短金利差（イールドスプレッド）データを取得"""
    start_time = time.time()
    result = us_interest_rate_spread_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )


# ===== Corporate Bond Market Distress Index (CMDI) =====


@router.get("/corporate-bond-market-distress-index")
def get_cmdi(force_refresh: bool = Query(False)):
    """企業債券市場ディストレス指数（CMDI）データを取得"""
    start_time = time.time()
    result = cmdi_service.get_data(force_refresh)
    response_time_ms = (time.time() - start_time) * 1000
    return JSONResponse(
        content={**result, "response_time_ms": round(response_time_ms, 2)},
        headers={"X-Cache": "HIT" if result.get("cached") else "MISS"},
    )
