"""
マーケットインパクト API

経済指標発表時の価格変動データを提供

エンドポイント:
    GET /api/market-impact/releases/{econalpha_id}    - 指標の発表履歴一覧（直近1年）
    GET /api/market-impact/chart                      - 発表時刻周辺のローソク足データ
    GET /api/market-impact/compare                    - 複数発表のオーバーレイ比較データ
    POST /api/market-impact/fetch                     - Dukascopyからデータ取得・保存
"""
import time
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from services.calendar.calendar_repository import calendar_repository
    from services.market.market_repository import market_repository
    from services.market.dukascopy_service import dukascopy_service
    from services.market.dukascopy_symbols import (
        DUKASCOPY_SYMBOLS,
        DUKASCOPY_CATEGORIES,
        DUKASCOPY_SUB_CATEGORIES,
        get_all_dukascopy_symbols,
        get_dukascopy_symbol_by_id,
        get_dukascopy_symbols_by_category,
        search_dukascopy_symbols,
    )
except ImportError:
    from backend.services.calendar.calendar_repository import calendar_repository
    from backend.services.market.market_repository import market_repository
    from backend.services.market.dukascopy_service import dukascopy_service
    from backend.services.market.dukascopy_symbols import (
        DUKASCOPY_SYMBOLS,
        DUKASCOPY_CATEGORIES,
        DUKASCOPY_SUB_CATEGORIES,
        get_all_dukascopy_symbols,
        get_dukascopy_symbol_by_id,
        get_dukascopy_symbols_by_category,
        search_dukascopy_symbols,
    )


router = APIRouter(prefix="/api/market-impact", tags=["MarketImpact"])

UTC = ZoneInfo("UTC")


class FetchRequest(BaseModel):
    """Dukascopyデータ取得リクエスト"""
    econalpha_id: str
    symbol_ids: List[str]
    days_back: int = 365  # 過去何日分を取得するか


@router.get("/symbols")
async def get_supported_symbols(
    category: Optional[str] = Query(None, description="カテゴリでフィルタ（forex, index, commodity, bond）"),
    search: Optional[str] = Query(None, description="検索クエリ"),
):
    """
    マーケットインパクト分析でサポートされている銘柄一覧

    Dukascopy対応の全銘柄（FX 68通貨ペア、指数 18、商品 13、債券 3）を返す

    Args:
        category: カテゴリフィルタ（forex, index, commodity, bond）
        search: 銘柄名検索

    Returns:
        {
            "symbols": [...],
            "categories": {...},
            "sub_categories": {...},
            "count": int
        }
    """
    if search:
        symbols = search_dukascopy_symbols(search)
    elif category:
        symbols = get_dukascopy_symbols_by_category(category)
    else:
        symbols = get_all_dukascopy_symbols()

    return {
        "symbols": symbols,
        "categories": DUKASCOPY_CATEGORIES,
        "sub_categories": DUKASCOPY_SUB_CATEGORIES,
        "count": len(symbols),
    }


@router.get("/sync-status")
async def get_sync_status(
    symbol_id: Optional[str] = Query(None, description="銘柄ID（省略時は全銘柄）"),
    interval: Optional[str] = Query(None, description="足種（1m, 5m）"),
):
    """
    銘柄の同期状態を取得

    バックグラウンド更新の状態を確認できる
    """
    if symbol_id and interval:
        status = dukascopy_service.get_sync_status(symbol_id, interval)
        if not status:
            return {"status": "not_synced", "symbol_id": symbol_id, "interval": interval}
        return status
    else:
        all_status = dukascopy_service.get_sync_status_all()
        return {
            "statuses": all_status,
            "count": len(all_status),
        }


@router.post("/sync/{symbol_id}")
async def sync_symbol_data(
    symbol_id: str,
    intervals: Optional[str] = Query("1m,5m", description="同期する足種（カンマ区切り）"),
):
    """
    銘柄の分足データを同期

    1年分のデータを取得してDBに保存する（同期的に実行）

    注意: この処理は10〜20秒程度かかります
    """
    # 銘柄の存在確認
    symbol = get_dukascopy_symbol_by_id(symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol_id}")

    interval_list = [i.strip() for i in intervals.split(",")]
    for interval in interval_list:
        if interval not in ["1m", "5m"]:
            raise HTTPException(status_code=400, detail=f"Invalid interval: {interval}")

    result = dukascopy_service.sync_symbol_data(symbol_id, interval_list)
    return result


@router.get("/releases/{econalpha_id}")
async def get_indicator_releases(
    econalpha_id: str,
    limit: int = Query(12, ge=1, le=24, description="取得件数（デフォルト12=1年分）"),
):
    """
    指標の発表履歴一覧を取得（直近1年分）

    1分足・5分足チャートのプルダウン選択用

    Args:
        econalpha_id: 指標ID (例: ism_manufacturing)
        limit: 取得件数

    Returns:
        {
            "econalpha_id": str,
            "releases": [
                {
                    "release_datetime": "2024-12-02T15:00:00Z",
                    "release_date": "2024-12-02",
                    "period_label": "Nov 2024",
                    "actual": 48.2,
                    "estimate": 47.5,
                    "previous": 48.7,
                    "surprise": 0.7,
                    "impact": "High"
                },
                ...
            ],
            "count": int
        }
    """
    start_time = time.time()

    # 1年前から現在まで
    from_date = date.today() - timedelta(days=365)
    to_date = date.today()

    # FMPのイベントデータから発表履歴を取得
    events = calendar_repository.get_events_by_econalpha_id(
        econalpha_id=econalpha_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )

    if not events:
        raise HTTPException(status_code=404, detail=f"No releases found for: {econalpha_id}")

    # レスポンス整形
    releases = []
    for event in events:
        datetime_utc = event.get("datetime_utc")
        if not datetime_utc:
            continue

        actual = event.get("actual")
        estimate = event.get("estimate")
        surprise = None
        if actual is not None and estimate is not None:
            surprise = round(float(actual) - float(estimate), 2)

        releases.append({
            "release_datetime": datetime_utc.isoformat() if hasattr(datetime_utc, 'isoformat') else str(datetime_utc),
            "release_date": datetime_utc.date().isoformat() if hasattr(datetime_utc, 'date') else str(datetime_utc)[:10],
            "period_label": event.get("event_period", ""),
            "actual": float(actual) if actual is not None else None,
            "estimate": float(estimate) if estimate is not None else None,
            "previous": float(event.get("previous")) if event.get("previous") is not None else None,
            "surprise": surprise,
            "impact": event.get("impact"),
            "event_name": event.get("event"),
        })

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "econalpha_id": econalpha_id,
            "releases": releases,
            "count": len(releases),
            "response_time_ms": round(response_time_ms, 2),
        }
    )


@router.get("/chart")
async def get_impact_chart(
    release_datetime: str = Query(..., description="発表日時（ISO8601形式）"),
    symbol_id: str = Query("usdjpy", description="銘柄ID"),
    interval: str = Query("1m", description="足種（1m=1分足, 5m=5分足）"),
):
    """
    発表時刻周辺のローソク足データを取得

    Args:
        release_datetime: 発表日時（例: 2024-12-02T15:00:00Z）
        symbol_id: 銘柄ID（例: usdjpy, gold, sp500）
        interval: 1m（±1時間）または 5m（±24時間）

    Returns:
        {
            "symbol_id": str,
            "interval": str,
            "release_datetime": str,
            "data": [
                {"timestamp": str, "open": float, "high": float, "low": float, "close": float, "volume": int},
                ...
            ],
            "release_index": int,  // 発表時刻のインデックス
            "count": int
        }
    """
    start_time = time.time()

    # パラメータ検証
    if interval not in ["1m", "5m"]:
        raise HTTPException(status_code=400, detail="interval must be '1m' or '5m'")

    if symbol_id not in dukascopy_service.get_supported_symbols():
        raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol_id}")

    try:
        release_dt = datetime.fromisoformat(release_datetime.replace("Z", "+00:00"))
        if release_dt.tzinfo is None:
            release_dt = release_dt.replace(tzinfo=UTC)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid release_datetime format")

    # 取得範囲を決定
    if interval == "1m":
        before_minutes = 60
        after_minutes = 60
    else:  # 5m
        before_minutes = 24 * 60
        after_minutes = 24 * 60

    start_time_range = release_dt - timedelta(minutes=before_minutes)
    end_time_range = release_dt + timedelta(minutes=after_minutes)

    # DBからデータ取得
    data = market_repository.get_intraday_data(
        symbol_id=symbol_id,
        interval=interval,
        start_time=start_time_range,
        end_time=end_time_range,
    )

    # データがない場合はDukascopyから取得を試みる
    if not data:
        # Dukascopyから取得
        fetch_result = dukascopy_service.fetch_around_release_time(
            symbol_id=symbol_id,
            release_time=release_dt,
            before_minutes=before_minutes,
            after_minutes=after_minutes,
            interval=interval,
        )

        if fetch_result.get("data"):
            # DBに保存
            raw_data = []
            for d in fetch_result["data"]:
                ts = d["timestamp"]
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                raw_data.append({
                    "timestamp": ts,
                    "open": d["open"],
                    "high": d["high"],
                    "low": d["low"],
                    "close": d["close"],
                    "volume": d.get("volume", 0),
                })

            dukascopy_service.save_to_db(symbol_id, raw_data, interval)
            data = fetch_result["data"]

    # 発表時刻のインデックスを特定
    release_index = None
    for i, d in enumerate(data):
        ts = d.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if ts and abs((ts - release_dt).total_seconds()) < (60 if interval == "1m" else 300):
            release_index = i
            break

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "symbol_id": symbol_id,
            "interval": interval,
            "release_datetime": release_datetime,
            "data": data,
            "release_index": release_index,
            "count": len(data),
            "response_time_ms": round(response_time_ms, 2),
        }
    )


@router.get("/compare")
async def get_compare_data(
    release_datetimes: str = Query(..., description="発表日時のカンマ区切りリスト"),
    symbol_id: str = Query("usdjpy", description="銘柄ID"),
    interval: str = Query("1m", description="足種（1m=1分足, 5m=5分足）"),
):
    """
    複数の発表日時のデータをオーバーレイ比較用に取得

    発表時刻を0点として正規化したデータを返す

    Args:
        release_datetimes: カンマ区切りの発表日時リスト（例: "2024-12-02T15:00:00Z,2024-11-04T15:00:00Z"）
        symbol_id: 銘柄ID
        interval: 1m または 5m

    Returns:
        {
            "symbol_id": str,
            "interval": str,
            "series": [
                {
                    "release_datetime": str,
                    "label": str,
                    "data": [
                        {"minutes_from_release": int, "close": float, "change_pct": float},
                        ...
                    ]
                },
                ...
            ]
        }
    """
    start_time = time.time()

    # パラメータ検証
    if interval not in ["1m", "5m"]:
        raise HTTPException(status_code=400, detail="interval must be '1m' or '5m'")

    if symbol_id not in dukascopy_service.get_supported_symbols():
        raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol_id}")

    datetime_list = [dt.strip() for dt in release_datetimes.split(",")]
    if len(datetime_list) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 release_datetimes allowed")

    # 取得範囲
    if interval == "1m":
        before_minutes = 60
        after_minutes = 60
    else:
        before_minutes = 24 * 60
        after_minutes = 24 * 60

    # 発表日時をパースして時間範囲リストを作成
    parsed_releases: List[tuple[str, datetime, datetime, datetime]] = []
    for dt_str in datetime_list:
        try:
            release_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            if release_dt.tzinfo is None:
                release_dt = release_dt.replace(tzinfo=UTC)
            start_range = release_dt - timedelta(minutes=before_minutes)
            end_range = release_dt + timedelta(minutes=after_minutes)
            parsed_releases.append((dt_str, release_dt, start_range, end_range))
        except ValueError:
            continue

    if not parsed_releases:
        return JSONResponse(
            content={
                "symbol_id": symbol_id,
                "interval": interval,
                "series": [],
                "count": 0,
                "response_time_ms": 0,
            }
        )

    # バッチクエリで全データを1回で取得（N+1解消）
    time_ranges = [(start_range, end_range) for _, _, start_range, end_range in parsed_releases]
    batch_data = market_repository.get_intraday_data_batch(
        symbol_id=symbol_id,
        interval=interval,
        time_ranges=time_ranges,
    )

    series = []
    missing_releases = []  # DBにデータがない発表日時

    for dt_str, release_dt, start_range, end_range in parsed_releases:
        key = start_range.isoformat()
        data = batch_data.get(key, [])

        if not data:
            missing_releases.append((dt_str, release_dt, start_range, end_range))
            continue

        # 発表時刻の価格を基準として正規化
        normalized_data = _normalize_compare_data(data, release_dt)
        if normalized_data:
            series.append({
                "release_datetime": dt_str,
                "label": release_dt.strftime("%Y/%m/%d"),
                "data": normalized_data,
            })

    # DBにデータがないものはDukascopyから取得
    for dt_str, release_dt, start_range, end_range in missing_releases:
        fetch_result = dukascopy_service.fetch_around_release_time(
            symbol_id=symbol_id,
            release_time=release_dt,
            before_minutes=before_minutes,
            after_minutes=after_minutes,
            interval=interval,
        )

        if fetch_result.get("data"):
            # DBに保存
            raw_data = []
            for d in fetch_result["data"]:
                ts = d["timestamp"]
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                raw_data.append({
                    "timestamp": ts,
                    "open": d["open"],
                    "high": d["high"],
                    "low": d["low"],
                    "close": d["close"],
                    "volume": d.get("volume", 0),
                })

            dukascopy_service.save_to_db(symbol_id, raw_data, interval)
            data = fetch_result["data"]

            # 正規化
            normalized_data = _normalize_compare_data(data, release_dt)
            if normalized_data:
                series.append({
                    "release_datetime": dt_str,
                    "label": release_dt.strftime("%Y/%m/%d"),
                    "data": normalized_data,
                })

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "symbol_id": symbol_id,
            "interval": interval,
            "series": series,
            "count": len(series),
            "response_time_ms": round(response_time_ms, 2),
        }
    )


def _normalize_compare_data(data: List[Dict], release_dt: datetime) -> List[Dict]:
    """
    比較用データを正規化（発表時刻を0点、変化率計算）

    Args:
        data: OHLCデータリスト
        release_dt: 発表日時

    Returns:
        正規化されたデータリスト
    """
    base_price = None
    normalized_data = []

    for d in data:
        ts = d.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

        if ts is None:
            continue

        # 発表時刻からの分数を計算
        diff_seconds = (ts - release_dt).total_seconds()
        minutes_from_release = int(diff_seconds / 60)

        close_price = d.get("close")
        if close_price is None:
            continue

        # 発表直前（-1分 〜 0分）の価格を基準にする
        if -1 <= minutes_from_release <= 0 and base_price is None:
            base_price = close_price

        normalized_data.append({
            "minutes_from_release": minutes_from_release,
            "close": close_price,
        })

    # 変化率を計算
    if base_price and base_price != 0:
        for item in normalized_data:
            change_pct = ((item["close"] - base_price) / base_price) * 100
            item["change_pct"] = round(change_pct, 4)

    return normalized_data


@router.post("/fetch")
async def fetch_dukascopy_data(request: FetchRequest):
    """
    Dukascopyから分足データを取得してDBに保存

    指標の発表履歴を元に、各発表時刻周辺のデータを取得

    Args:
        econalpha_id: 指標ID
        symbol_ids: 銘柄IDのリスト
        days_back: 過去何日分を取得するか（デフォルト365日）
    """
    start_time = time.time()

    # 発表履歴を取得
    from_date = date.today() - timedelta(days=request.days_back)
    events = calendar_repository.get_events_by_econalpha_id(
        econalpha_id=request.econalpha_id,
        from_date=from_date,
        to_date=date.today(),
        limit=24,
    )

    if not events:
        raise HTTPException(status_code=404, detail=f"No events found for: {request.econalpha_id}")

    results = []

    for event in events:
        datetime_utc = event.get("datetime_utc")
        if not datetime_utc:
            continue

        for symbol_id in request.symbol_ids:
            if symbol_id not in dukascopy_service.get_supported_symbols():
                continue

            result = dukascopy_service.fetch_for_indicator_release(
                symbol_id=symbol_id,
                release_time=datetime_utc,
            )
            results.append(result)

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "econalpha_id": request.econalpha_id,
            "symbol_ids": request.symbol_ids,
            "events_count": len(events),
            "fetch_results": results,
            "response_time_ms": round(response_time_ms, 2),
        }
    )


@router.delete("/cleanup")
async def cleanup_old_data(days: int = Query(365, ge=30, le=730)):
    """
    古い分足データを削除

    Args:
        days: 保持する日数（デフォルト365日）
    """
    from sqlalchemy import text
    from core.database import SessionLocal

    cutoff_date = datetime.now(UTC) - timedelta(days=days)

    session = SessionLocal()
    try:
        result = session.execute(
            text("""
                DELETE FROM timeseries.market_intraday_data
                WHERE timestamp < :cutoff_date
                RETURNING symbol_id
            """),
            {"cutoff_date": cutoff_date}
        )
        deleted_count = result.rowcount
        session.commit()

        return {
            "status": "success",
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
