"""
FMP次回発表日取得ユーティリティ（中国向け）

indicator_event_mappingテーブルのfmp_event_patternsを使用して、
FMP APIから次回発表日を取得する共通関数を提供。

使用方法:
    from services.china.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern

    # パターンを指定して次回発表日を取得
    next_release = get_next_release_by_pattern('Loan Prime Rate 1Y', country='CN')
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

# タイムゾーン
CST = ZoneInfo("Asia/Shanghai")
UTC = ZoneInfo("UTC")
JST = ZoneInfo("Asia/Tokyo")

# キャッシュTTL（1日）
NEXT_RELEASE_CACHE_TTL = 86400

# 発表後の更新チェック期間（分）
UPDATE_WINDOW_MINUTES = 10


def get_next_release_by_pattern(
    event_pattern: str,
    use_cache: bool = True,
    country: str = "CN"
) -> Optional[Dict[str, Any]]:
    """
    FMPイベントパターンで次回発表日を取得

    まずDBのeconomic_calendar_eventsテーブルから検索し、
    なければFMP APIを呼び出す。

    Args:
        event_pattern: イベント名のパターン（例: "Loan Prime Rate 1Y"）
        use_cache: Redisキャッシュを使用するか
        country: 国コード（デフォルト: "CN"）

    Returns:
        次回発表日情報
    """
    cache_key = f"fmp:next_release:pattern:{country}:{event_pattern.lower().replace(' ', '_')}"

    if use_cache:
        cached = redis_client.get(cache_key)
        if cached:
            return cached

    try:
        # まずDBから検索（より信頼性が高い）
        result = _get_next_release_from_db(event_pattern, country)
        if result:
            if use_cache:
                redis_client.set(cache_key, result, expire=NEXT_RELEASE_CACHE_TTL)
            return result

        # DBになければAPIから取得
        from services.calendar.fmp_service import fmp_service

        today = date.today()
        events = fmp_service.fetch_calendar(
            today,
            today + timedelta(days=90),
            country=country
        )

        candidates = []
        pattern_lower = event_pattern.lower()

        for event in events:
            if event.get("country") != country:
                continue

            event_name = event.get("event", "")
            if pattern_lower not in event_name.lower():
                continue

            if event.get("actual") is not None:
                continue

            dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
            if dt_utc and dt_utc.date() >= today:
                dt_jst = dt_utc.astimezone(JST)
                dt_cst = dt_utc.astimezone(CST)
                candidates.append({
                    "date": dt_utc.strftime("%Y-%m-%d"),
                    "datetime_utc": dt_utc.isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
                    "datetime_cst": dt_cst.isoformat(),
                    "time_cst": dt_cst.strftime("%H:%M"),
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
        print(f"[CN FMP Utils] Error fetching next release by pattern '{event_pattern}' for country '{country}': {e}")
        return None


def _get_next_release_from_db(
    event_pattern: str,
    country: str = "CN"
) -> Optional[Dict[str, Any]]:
    """
    DBのeconomic_calendar_eventsテーブルから次回発表日を取得
    """
    try:
        from core.database import get_db_connection

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT event, datetime_utc, estimate
                FROM economic_calendar_events
                WHERE country = %s
                  AND event ILIKE %s
                  AND actual IS NULL
                  AND datetime_utc >= NOW()
                ORDER BY datetime_utc ASC
                LIMIT 1
            """, (country, f"%{event_pattern}%"))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            event_name = row[0]
            dt_utc = row[1]
            estimate = row[2]

            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=UTC)

            dt_jst = dt_utc.astimezone(JST)
            dt_cst = dt_utc.astimezone(CST)

            return {
                "date": dt_utc.strftime("%Y-%m-%d"),
                "datetime_utc": dt_utc.isoformat(),
                "datetime_jst": dt_jst.isoformat(),
                "time_jst": dt_jst.strftime("%H:%M"),
                "datetime_cst": dt_cst.isoformat(),
                "time_cst": dt_cst.strftime("%H:%M"),
                "label": event_name,
                "estimate": float(estimate) if estimate is not None else None,
            }

    except Exception as e:
        print(f"[CN FMP Utils] Error fetching from DB: {e}")
        return None


def should_refresh_by_pattern(
    event_pattern: str,
    last_updated_str: str,
    country: str = "CN",
    max_age_hours: float = 168.0,
) -> bool:
    """
    FMPイベントパターンに基づく更新判定
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        last_updated = datetime.fromisoformat(last_updated_str)
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=JST)

        now = datetime.now(JST)

        # max-age フォールバック（発表レース凍結の自己回復）:
        # 発表時刻ちょうどの再取得でソース(NBS/FMPカレンダー等)未反映のまま
        # last_updated=now を刻むと、下のスケジュール判定が「発表消化済み」と誤認し
        # 次回発表まで永久凍結する（CN utils は従来 max-age を持たず、四半期の経常収支では
        # 最大3ヶ月凍結した）。一定時間で必ず True を返し自己回復させる。
        if (now - last_updated).total_seconds() > max_age_hours * 60 * 60:
            return True

        with SessionLocal() as session:
            params = {"country": country, "pattern": f"%{event_pattern}%"}

            # 1. actual IS NOT NULLの直近イベント（従来の判定）
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
            row = session.execute(query, params).fetchone()

            if row:
                dt_utc = row[0]
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=UTC)
                release_datetime = dt_utc.astimezone(JST)
                if now >= release_datetime and last_updated < release_datetime:
                    return True

            # 2. actual IS NULLだが発表時刻を過ぎたイベントもチェック
            query_pending = text("""
                SELECT datetime_utc, event
                FROM economic_calendar_events
                WHERE country = :country
                  AND event ILIKE :pattern
                  AND actual IS NULL
                  AND datetime_utc <= NOW()
                ORDER BY datetime_utc DESC
                LIMIT 1
            """)
            row_pending = session.execute(query_pending, params).fetchone()

            if row_pending:
                dt_utc_pending = row_pending[0]
                if dt_utc_pending.tzinfo is None:
                    dt_utc_pending = dt_utc_pending.replace(tzinfo=UTC)
                pending_release = dt_utc_pending.astimezone(JST)
                if now >= pending_release and last_updated < pending_release:
                    return True

            return False

    except Exception as e:
        print(f"[CN FMP Utils] Error checking refresh by pattern '{event_pattern}' for country '{country}': {e}")
        return False


def invalidate_next_release_cache(event_pattern: str, country: str = "CN") -> bool:
    """次回発表日キャッシュを無効化"""
    cache_key = f"fmp:next_release:pattern:{country}:{event_pattern.lower().replace(' ', '_')}"
    return redis_client.delete(cache_key)
