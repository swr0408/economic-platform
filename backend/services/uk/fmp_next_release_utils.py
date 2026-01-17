"""
FMP次回発表日取得ユーティリティ（イギリス向け）

indicator_event_mappingテーブルのfmp_event_patternsを使用して、
FMP APIから次回発表日を取得する共通関数を提供。

使用方法:
    from services.uk.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern

    # パターンを指定して次回発表日を取得
    next_release = get_next_release_by_pattern('Interest Rate Decision', country='GB')
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

# タイムゾーン
LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")
JST = ZoneInfo("Asia/Tokyo")

# キャッシュTTL（1日）
NEXT_RELEASE_CACHE_TTL = 86400

# 発表後の更新チェック期間（分）
# BOE金利決定は12:00 ロンドン時間に発表
UPDATE_WINDOW_MINUTES = 10


def get_next_release_by_pattern(
    event_pattern: str,
    use_cache: bool = True,
    country: str = "GB"
) -> Optional[Dict[str, Any]]:
    """
    FMPイベントパターンで次回発表日を取得

    Args:
        event_pattern: イベント名のパターン（例: "Interest Rate Decision"）
        use_cache: Redisキャッシュを使用するか
        country: 国コード（デフォルト: "GB"）

    Returns:
        次回発表日情報
    """
    cache_key = f"fmp:next_release:pattern:{country}:{event_pattern.lower().replace(' ', '_')}"

    if use_cache:
        cached = redis_client.get(cache_key)
        if cached:
            return cached

    try:
        from services.calendar.fmp_service import fmp_service

        today = date.today()
        events = fmp_service.fetch_calendar(
            today,
            today + timedelta(days=90),
            country=country
        )

        candidates = []
        pattern_lower = event_pattern.lower()

        # FMP APIでは country パラメータに "GB" を渡しても、
        # レスポンスの country フィールドは "UK" で返ってくる
        valid_countries = {country, "UK"} if country == "GB" else {country}

        for event in events:
            if event.get("country") not in valid_countries:
                continue

            event_name = event.get("event", "")
            if pattern_lower not in event_name.lower():
                continue

            if event.get("actual") is not None:
                continue

            dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
            if dt_utc and dt_utc.date() >= today:
                dt_jst = dt_utc.astimezone(JST)
                dt_london = dt_utc.astimezone(LONDON)
                candidates.append({
                    "date": dt_utc.strftime("%Y-%m-%d"),
                    "datetime_utc": dt_utc.isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
                    "datetime_london": dt_london.isoformat(),
                    "time_london": dt_london.strftime("%H:%M"),
                    "label": event_name,
                    "estimate": event.get("estimate"),
                    "_dt": dt_utc,
                })

        if candidates:
            candidates.sort(key=lambda x: x["_dt"])
            result = candidates[0]
            del result["_dt"]

            if use_cache:
                redis_client.set(cache_key, result, expire=NEXT_RELEASE_CACHE_TTL)

            return result

        return None

    except Exception as e:
        print(f"[UK FMP Utils] Error fetching next release by pattern '{event_pattern}' for country '{country}': {e}")
        return None


def should_refresh_by_pattern(
    event_pattern: str,
    last_updated_str: str,
    country: str = "GB"
) -> bool:
    """
    FMPイベントパターンに基づく更新判定

    Args:
        event_pattern: イベント名のパターン
        last_updated_str: 最終更新日時のISO文字列
        country: 国コード（デフォルト: "GB"）

    Returns:
        True: 更新が必要
        False: キャッシュ有効
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        last_updated = datetime.fromisoformat(last_updated_str)
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=JST)

        now = datetime.now(JST)

        with SessionLocal() as session:
            query = text("""
                SELECT datetime_utc, event, actual
                FROM economic_calendar_events
                WHERE country = :country
                  AND event ILIKE :pattern
                  AND actual IS NOT NULL
                  AND datetime_utc <= NOW()
                ORDER BY datetime_utc DESC
                LIMIT 1
            """)
            row = session.execute(query, {"country": country, "pattern": f"%{event_pattern}%"}).fetchone()

            if not row:
                return False

            dt_utc = row[0]
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=UTC)

            release_datetime = dt_utc.astimezone(JST)

            if now < release_datetime:
                return False

            update_window_end = release_datetime + timedelta(minutes=UPDATE_WINDOW_MINUTES)

            if now <= update_window_end:
                if last_updated < release_datetime:
                    return True
            else:
                if last_updated < release_datetime:
                    return True

            return False

    except Exception as e:
        print(f"[UK FMP Utils] Error checking refresh by pattern '{event_pattern}' for country '{country}': {e}")
        return False


def invalidate_next_release_cache(event_pattern: str, country: str = "GB") -> bool:
    """
    次回発表日キャッシュを無効化

    Args:
        event_pattern: イベント名のパターン
        country: 国コード

    Returns:
        成功したかどうか
    """
    cache_key = f"fmp:next_release:pattern:{country}:{event_pattern.lower().replace(' ', '_')}"
    return redis_client.delete(cache_key)
