"""
市場データAPI（DB版）
PostgreSQL + TimescaleDB を使用した銘柄データ取得エンドポイント

エンドポイント:
    GET /api/market/symbols           - 銘柄リスト取得
    GET /api/market/{symbol_id}/daily - 個別銘柄の日足データ取得
    GET /api/market/dashboard         - 全銘柄の最新データ（バッチ）
    POST /api/market/update           - 全銘柄を手動更新
"""
import time
from typing import Optional
from fastapi import APIRouter, Path, Query, HTTPException
from fastapi.responses import JSONResponse

try:
    from backend.services.market.yfinance_service_db import yfinance_service_db
    from backend.services.market.market_repository import market_repository
    from backend.services.market.market_scheduler import market_scheduler
except ImportError:
    from services.market.yfinance_service_db import yfinance_service_db
    from services.market.market_repository import market_repository
    from services.market.market_scheduler import market_scheduler


router = APIRouter(prefix="/api/market", tags=["Market"])


# カテゴリ定義
SYMBOL_CATEGORIES = {
    "forex": "為替",
    "index": "株価指数",
    "commodity": "商品",
    "bond": "債券",
}

SYMBOL_SUB_CATEGORIES = {
    "forex_usd": "ドルストレート",
    "forex_jpy": "クロス円",
    "forex_cross": "その他クロス",
    "forex_index": "通貨インデックス",
    "index_us": "米国株価指数",
    "index_asia": "日本・アジア株価指数",
    "index_europe": "欧州株価指数",
    "calculated_index": "計算値（指数）",
    "bond": "債券利回り",
    "commodity_metal": "貴金属",
    "commodity_energy": "エネルギー",
    "calculated_commodity": "計算値（商品）",
}


@router.get("/symbols")
async def get_symbols(
    category: Optional[str] = Query(None, description="カテゴリでフィルタ（forex, index, commodity, bond）"),
    search: Optional[str] = Query(None, description="検索クエリ"),
):
    """
    銘柄リストを取得（DBから）

    Returns:
        {
            "symbols": [...],
            "categories": {...},
            "sub_categories": {...},
            "total": int
        }
    """
    all_symbols = market_repository.get_all_symbols()

    # フィルタリング
    if search:
        search_lower = search.lower()
        symbols = [
            s for s in all_symbols
            if search_lower in s["name"].lower()
            or search_lower in s["name_en"].lower()
            or search_lower in s["id"].lower()
        ]
    elif category:
        symbols = [s for s in all_symbols if s["category"] == category]
    else:
        symbols = all_symbols

    return {
        "symbols": symbols,
        "categories": SYMBOL_CATEGORIES,
        "sub_categories": SYMBOL_SUB_CATEGORIES,
        "total": len(symbols),
    }


@router.get("/dashboard")
async def get_market_dashboard(
    symbols: Optional[str] = Query(None, description="カンマ区切りの銘柄IDリスト"),
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """
    市場データダッシュボード（バッチ取得）

    指定した銘柄の日足データをまとめて取得。
    symbols を省略すると全銘柄のデータを返す。
    """
    start_time = time.time()

    if symbols:
        symbol_ids = [s.strip() for s in symbols.split(",")]
        result = yfinance_service_db.get_multiple_daily_data(symbol_ids, force_refresh)
    else:
        all_symbols = market_repository.get_all_symbols()
        symbol_ids = [s["id"] for s in all_symbols]
        result = yfinance_service_db.get_multiple_daily_data(symbol_ids, force_refresh)

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


@router.get("/{symbol_id}/daily")
async def get_symbol_daily_data(
    symbol_id: str = Path(..., description="銘柄ID（例: usdjpy, sp500）"),
    force_refresh: bool = Query(False, description="キャッシュを無視して再取得"),
):
    """
    個別銘柄の日足データを取得
    """
    start_time = time.time()

    # 銘柄の存在確認
    symbol_info = market_repository.get_symbol(symbol_id)
    if not symbol_info:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol_id}")

    result = yfinance_service_db.get_daily_data(symbol_id, force_refresh)

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
async def get_symbol_cache_status(
    symbol_id: str = Path(..., description="銘柄ID"),
):
    """
    銘柄のキャッシュ・DB状態を取得
    """
    symbol_info = market_repository.get_symbol(symbol_id)
    if not symbol_info:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol_id}")

    return yfinance_service_db.get_cache_status(symbol_id)


@router.post("/{symbol_id}/refresh")
async def refresh_symbol_cache(
    symbol_id: str = Path(..., description="銘柄ID"),
):
    """
    銘柄のデータを強制更新（yfinanceから再取得）
    """
    symbol_info = market_repository.get_symbol(symbol_id)
    if not symbol_info:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol_id}")

    # キャッシュを無効化
    yfinance_service_db.invalidate_cache(symbol_id)

    # 再取得
    result = yfinance_service_db.get_daily_data(symbol_id, force_refresh=True)

    return {
        "success": not result.get("error"),
        "message": f"Data refreshed for {symbol_id}" if not result.get("error") else result.get("error"),
        "data_count": len(result.get("data", [])),
        "source": result.get("source"),
    }


@router.post("/update")
async def update_all_symbols(
    force_refresh: bool = Query(True, description="強制更新するかどうか"),
):
    """
    全銘柄のデータを手動更新

    スケジューラーとは別に、手動で全銘柄を更新する。
    """
    result = market_scheduler.run_now(force_refresh)

    return {
        "success": result["failed_count"] == 0,
        "success_count": result["success_count"],
        "failed_count": result["failed_count"],
        "total": result["total"],
        "duration_seconds": result["duration_seconds"],
        "errors": result["errors"][:10] if result["errors"] else [],  # 最初の10件のみ
    }


@router.delete("/cache")
async def invalidate_all_cache():
    """
    全銘柄のRedisキャッシュを無効化
    """
    count = yfinance_service_db.invalidate_all_cache()
    return {
        "success": True,
        "invalidated_count": count,
    }


@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    スケジューラーの状態を取得
    """
    return {
        "is_running": market_scheduler.is_running,
        "next_run_time": market_scheduler.get_next_run_time(),
    }
