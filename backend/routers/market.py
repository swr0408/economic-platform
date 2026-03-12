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
from fastapi.responses import JSONResponse

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
