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
