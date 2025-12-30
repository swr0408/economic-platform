"""
経済カレンダー API

エンドポイント:
    GET /api/calendar/events           - イベント一覧取得
    GET /api/calendar/events/{id}      - 指標別イベント取得
    GET /api/calendar/releases/{id}    - 指標発表履歴取得
    GET /api/calendar/candidates       - 指標候補一覧取得
    GET /api/calendar/mappings         - マッピング一覧取得
    GET /api/calendar/sync/status      - 同期状態取得
    POST /api/calendar/sync/run        - 手動同期実行
    POST /api/calendar/backfill        - バックフィル実行
"""
import time
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

try:
    from services.calendar.calendar_repository import calendar_repository
    from services.calendar.calendar_scheduler import calendar_scheduler
except ImportError:
    from backend.services.calendar.calendar_repository import calendar_repository
    from backend.services.calendar.calendar_scheduler import calendar_scheduler


router = APIRouter(prefix="/api/calendar", tags=["Calendar"])


@router.get("/events")
async def get_events(
    country: str = Query(..., description="国コード（US, JP, EU等）"),
    from_date: Optional[date] = Query(None, description="開始日（YYYY-MM-DD）"),
    to_date: Optional[date] = Query(None, description="終了日（YYYY-MM-DD）"),
    limit: int = Query(100, ge=1, le=1000, description="取得件数"),
):
    """
    国別の経済イベント一覧を取得

    Returns:
        {
            "events": [...],
            "count": int,
            "country": str
        }
    """
    start_time = time.time()

    events = calendar_repository.get_events_by_country(
        country=country.upper(),
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )

    # datetime を文字列に変換
    for event in events:
        if event.get("datetime_utc"):
            event["datetime_utc"] = event["datetime_utc"].isoformat()
        if event.get("ingested_at"):
            event["ingested_at"] = event["ingested_at"].isoformat()

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "events": events,
            "count": len(events),
            "country": country.upper(),
            "response_time_ms": round(response_time_ms, 2),
        }
    )


@router.get("/events/{econalpha_id}")
async def get_events_by_indicator(
    econalpha_id: str,
    from_date: Optional[date] = Query(None, description="開始日（YYYY-MM-DD）"),
    to_date: Optional[date] = Query(None, description="終了日（YYYY-MM-DD）"),
    limit: int = Query(100, ge=1, le=500, description="取得件数"),
):
    """
    EconAlpha指標IDに紐づくイベントを取得

    Args:
        econalpha_id: EconAlphaの指標ID（ism_manufacturing等）

    Returns:
        {
            "econalpha_id": str,
            "events": [...],
            "count": int
        }
    """
    start_time = time.time()

    # マッピング確認
    mapping = calendar_repository.get_mapping_by_econalpha_id(econalpha_id)
    if not mapping:
        raise HTTPException(status_code=404, detail=f"Mapping not found for: {econalpha_id}")

    events = calendar_repository.get_events_by_econalpha_id(
        econalpha_id=econalpha_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )

    # datetime を文字列に変換
    for event in events:
        if event.get("datetime_utc"):
            event["datetime_utc"] = event["datetime_utc"].isoformat()

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "econalpha_id": econalpha_id,
            "econalpha_name": mapping.get("econalpha_name"),
            "country": mapping.get("country"),
            "frequency": mapping.get("frequency"),
            "events": events,
            "count": len(events),
            "response_time_ms": round(response_time_ms, 2),
        }
    )


@router.get("/releases/{econalpha_id}")
async def get_indicator_releases(
    econalpha_id: str,
    from_date: Optional[date] = Query(None, description="開始日（YYYY-MM-DD）"),
    to_date: Optional[date] = Query(None, description="終了日（YYYY-MM-DD）"),
    limit: int = Query(100, ge=1, le=500, description="取得件数"),
):
    """
    指標発表履歴を取得（1分足/5分足表示用）

    Args:
        econalpha_id: EconAlphaの指標ID

    Returns:
        {
            "econalpha_id": str,
            "releases": [...],
            "count": int
        }
    """
    start_time = time.time()

    releases = calendar_repository.get_indicator_releases(
        econalpha_id=econalpha_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )

    # datetime を文字列に変換
    for release in releases:
        if release.get("release_datetime"):
            release["release_datetime"] = release["release_datetime"].isoformat()
        if release.get("release_date"):
            release["release_date"] = release["release_date"].isoformat()

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "econalpha_id": econalpha_id,
            "releases": releases,
            "count": len(releases),
            "response_time_ms": round(response_time_ms, 2),
        }
    )


@router.get("/candidates")
async def get_indicator_candidates(
    country: Optional[str] = Query(None, description="国コード（US, JP, EU等）"),
    min_occurrences: int = Query(1, ge=1, description="最小出現回数"),
):
    """
    指標候補一覧を取得

    過去1年間のイベントから集計した指標一覧

    Returns:
        {
            "candidates": [...],
            "count": int
        }
    """
    start_time = time.time()

    candidates = calendar_repository.get_indicator_candidates(
        country=country.upper() if country else None,
        min_occurrences=min_occurrences,
    )

    # datetime を文字列に変換
    for candidate in candidates:
        if candidate.get("first_seen_utc"):
            candidate["first_seen_utc"] = candidate["first_seen_utc"].isoformat()
        if candidate.get("last_seen_utc"):
            candidate["last_seen_utc"] = candidate["last_seen_utc"].isoformat()

    response_time_ms = (time.time() - start_time) * 1000

    return JSONResponse(
        content={
            "candidates": candidates,
            "count": len(candidates),
            "response_time_ms": round(response_time_ms, 2),
        }
    )


@router.get("/mappings")
async def get_mappings(
    country: Optional[str] = Query(None, description="国コード（US, JP, EU等）"),
):
    """
    EconAlpha指標マッピング一覧を取得

    Returns:
        {
            "mappings": [...],
            "count": int
        }
    """
    mappings = calendar_repository.get_all_mappings(
        country=country.upper() if country else None,
    )

    return {
        "mappings": mappings,
        "count": len(mappings),
    }


@router.get("/sync/status")
async def get_sync_status():
    """
    同期状態を取得

    Returns:
        {
            "provider": "FMP",
            "last_success_at": str,
            "last_range_from": str,
            "last_range_to": str,
            "records_count": int,
            "scheduler_running": bool,
            "next_run_times": {...}
        }
    """
    sync_state = calendar_repository.get_sync_state("FMP")

    if sync_state:
        if sync_state.get("last_success_at"):
            sync_state["last_success_at"] = sync_state["last_success_at"].isoformat()
        if sync_state.get("last_range_from"):
            sync_state["last_range_from"] = sync_state["last_range_from"].isoformat()
        if sync_state.get("last_range_to"):
            sync_state["last_range_to"] = sync_state["last_range_to"].isoformat()
        if sync_state.get("updated_at"):
            sync_state["updated_at"] = sync_state["updated_at"].isoformat()

    return {
        "sync_state": sync_state,
        "scheduler_running": calendar_scheduler.is_running,
        "next_run_times": calendar_scheduler.get_next_run_times() if calendar_scheduler.is_running else None,
    }


@router.post("/sync/run")
async def run_sync(
    background_tasks: BackgroundTasks,
    days: int = Query(14, ge=1, le=365, description="同期日数"),
):
    """
    手動で同期を実行（直近N日）

    バックグラウンドで実行し、即座にレスポンスを返す
    """
    from datetime import date, timedelta

    today = date.today()
    start_date = today - timedelta(days=days)

    def sync_task():
        try:
            result = calendar_scheduler.sync_range(start_date, today)
            print(f"[CalendarAPI] Sync completed: {result['upserted_count']} events")
        except Exception as e:
            print(f"[CalendarAPI] Sync failed: {e}")

    background_tasks.add_task(sync_task)

    return {
        "status": "started",
        "message": f"Syncing calendar from {start_date} to {today}",
        "days": days,
    }


@router.post("/backfill")
async def run_backfill(
    background_tasks: BackgroundTasks,
    days: int = Query(365, ge=1, le=365, description="バックフィル日数"),
):
    """
    バックフィルを実行（過去N日分を取得）

    初回セットアップ時に使用
    バックグラウンドで実行し、即座にレスポンスを返す
    """
    def backfill_task():
        try:
            result = calendar_scheduler.backfill(days=days)
            print(f"[CalendarAPI] Backfill completed: {result['upserted_count']} events")
        except Exception as e:
            print(f"[CalendarAPI] Backfill failed: {e}")
            import traceback
            traceback.print_exc()

    background_tasks.add_task(backfill_task)

    return {
        "status": "started",
        "message": f"Backfilling {days} days of calendar data",
        "days": days,
    }


@router.post("/releases/sync/{econalpha_id}")
async def sync_indicator_releases(econalpha_id: str):
    """
    指標発表履歴を同期

    economic_calendar_eventsからindicator_releasesへコピー
    """
    # マッピング確認
    mapping = calendar_repository.get_mapping_by_econalpha_id(econalpha_id)
    if not mapping:
        raise HTTPException(status_code=404, detail=f"Mapping not found for: {econalpha_id}")

    count = calendar_repository.sync_indicator_releases(econalpha_id)

    return {
        "econalpha_id": econalpha_id,
        "synced_count": count,
        "message": f"Synced {count} releases for {econalpha_id}",
    }
