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
except ImportError:
    from services.market.fear_greed_service import fear_greed_service


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
