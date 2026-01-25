"""
FMP次回発表日取得ユーティリティ（ユーロ圏向け）

indicator_event_mappingテーブルのfmp_event_patternsを使用して、
FMP APIから次回発表日を取得する共通関数を提供。

使用方法:
    from services.eurozone.fmp_next_release_utils import get_next_release_from_fmp, should_refresh_by_fmp_schedule

    # 指標IDを指定して次回発表日を取得
    next_release = get_next_release_from_fmp('eu_ecb_rate')
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

# タイムゾーン
CET = ZoneInfo("Europe/Berlin")  # 中央ヨーロッパ時間
UTC = ZoneInfo("UTC")
JST = ZoneInfo("Asia/Tokyo")

# キャッシュTTL（1日）
NEXT_RELEASE_CACHE_TTL = 86400

# 発表後の更新チェック期間（分）
# ECB金利決定は21:15-21:25 CET頃に発表
UPDATE_WINDOW_MINUTES = 10


def _get_country_from_mapping(econalpha_id: str) -> Optional[str]:
    """
    indicator_event_mappingから国コードを取得

    Args:
        econalpha_id: EconAlpha指標ID

    Returns:
        国コード（マッピングがなければNone）
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            query = text("""
                SELECT country
                FROM indicator_event_mapping
                WHERE econalpha_id = :id AND is_active = TRUE
            """)
            row = session.execute(query, {"id": econalpha_id}).fetchone()

            if row and row[0]:
                return row[0]
            return None

    except Exception as e:
        print(f"Error fetching country for {econalpha_id}: {e}")
        return None


def get_fmp_event_patterns(econalpha_id: str) -> Optional[List[str]]:
    """
    indicator_event_mappingからFMPイベントパターンを取得

    Args:
        econalpha_id: EconAlpha指標ID

    Returns:
        FMPイベントパターンのリスト。マッピングがなければNone
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            query = text("""
                SELECT fmp_event_patterns
                FROM indicator_event_mapping
                WHERE econalpha_id = :id AND is_active = TRUE
            """)
            row = session.execute(query, {"id": econalpha_id}).fetchone()

            if row and row[0]:
                return row[0]
            return None

    except Exception as e:
        print(f"Error fetching FMP event patterns for {econalpha_id}: {e}")
        return None


def get_next_release_from_fmp(
    econalpha_id: str,
    patterns: Optional[List[str]] = None,
    use_cache: bool = True,
    country: str = None
) -> Optional[Dict[str, Any]]:
    """
    FMP APIから次回発表日を取得（ユーロ圏向け）

    Args:
        econalpha_id: EconAlpha指標ID（マッピングテーブルから自動取得）
        patterns: FMPイベントパターン（指定しない場合はマッピングテーブルから取得）
        use_cache: Redisキャッシュを使用するか
        country: 国コード（指定しない場合はマッピングテーブルから取得、またはデフォルトEU）

    Returns:
        次回発表日情報
    """
    cache_key = f"fmp:next_release:{econalpha_id}"

    # キャッシュチェック
    if use_cache:
        cached = redis_client.get(cache_key)
        if cached:
            return cached

    # パターンが指定されていなければマッピングから取得
    if patterns is None:
        patterns = get_fmp_event_patterns(econalpha_id)

    if not patterns:
        print(f"No FMP event patterns found for {econalpha_id}")
        return None

    # 国コードを決定（マッピングから取得、なければデフォルト）
    if country is None:
        country = _get_country_from_mapping(econalpha_id)
        if country is None:
            country = "EU"

    try:
        from services.calendar.fmp_service import fmp_service

        today = date.today()
        # 90日先までのイベントを取得
        events = fmp_service.fetch_calendar(
            today,
            today + timedelta(days=90),
            country=country
        )

        # 対象イベントを収集
        candidates = []
        for event in events:
            if event.get("country") != country:
                continue

            event_name = event.get("event", "")
            event_name_lower = event_name.lower()

            # パターンマッチング
            matched = False
            for pattern in patterns:
                clean_pattern = pattern.strip('%').lower()
                if clean_pattern in event_name_lower:
                    matched = True
                    break

            if not matched:
                continue

            # 将来のイベント（actual が None）のみ
            if event.get("actual") is not None:
                continue

            dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
            if dt_utc and dt_utc.date() >= today:
                dt_jst = dt_utc.astimezone(JST)
                dt_cet = dt_utc.astimezone(CET)
                candidates.append({
                    "date": dt_utc.strftime("%Y-%m-%d"),
                    "datetime_utc": dt_utc.isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
                    "datetime_cet": dt_cet.isoformat(),
                    "time_cet": dt_cet.strftime("%H:%M"),
                    "label": event_name,
                    "estimate": event.get("estimate"),
                    "_dt": dt_utc,
                })

        # 日付順でソートして最も近いイベントを返す
        if candidates:
            candidates.sort(key=lambda x: x["_dt"])
            result = candidates[0]
            del result["_dt"]

            # キャッシュに保存
            if use_cache:
                redis_client.set(cache_key, result, expire=NEXT_RELEASE_CACHE_TTL)

            return result

        return None

    except Exception as e:
        print(f"Error fetching next release from FMP for {econalpha_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_last_release_from_fmp(
    econalpha_id: str,
    patterns: Optional[List[str]] = None,
    country: str = None,
) -> Optional[Dict[str, Any]]:
    """
    FMP APIから直近の発表日時を取得（過去のイベント）

    Args:
        econalpha_id: EconAlpha指標ID
        patterns: FMPイベントパターン
        country: 国コード（指定しない場合はマッピングテーブルから取得）

    Returns:
        直近の発表日時情報
    """
    if patterns is None:
        patterns = get_fmp_event_patterns(econalpha_id)

    if not patterns:
        return None

    # 国コードを決定
    if country is None:
        country = _get_country_from_mapping(econalpha_id)
        if country is None:
            country = "EU"

    try:
        from services.calendar.fmp_service import fmp_service

        today = date.today()
        # 過去90日分を取得
        events = fmp_service.fetch_calendar(
            today - timedelta(days=90),
            today,
            country=country
        )

        candidates = []
        for event in events:
            if event.get("country") != country:
                continue

            event_name = event.get("event", "")
            event_name_lower = event_name.lower()

            # パターンマッチング
            matched = False
            for pattern in patterns:
                clean_pattern = pattern.strip('%').lower()
                if clean_pattern in event_name_lower:
                    matched = True
                    break

            if not matched:
                continue

            # 過去のイベント（actual が入っている）
            if event.get("actual") is None:
                continue

            dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
            if dt_utc:
                dt_jst = dt_utc.astimezone(JST)
                dt_cet = dt_utc.astimezone(CET)
                candidates.append({
                    "date": dt_utc.strftime("%Y-%m-%d"),
                    "datetime_utc": dt_utc.isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
                    "datetime_cet": dt_cet.isoformat(),
                    "time_cet": dt_cet.strftime("%H:%M"),
                    "label": event_name,
                    "actual": event.get("actual"),
                    "_dt": dt_utc,
                })

        if candidates:
            candidates.sort(key=lambda x: x["_dt"], reverse=True)
            result = candidates[0]
            del result["_dt"]
            return result

        return None

    except Exception as e:
        print(f"Error fetching last release from FMP for {econalpha_id}: {e}")
        return None


def should_refresh_by_fmp_schedule(
    econalpha_id: str,
    last_updated_str: str,
) -> bool:
    """
    FMPスケジュールに基づく更新判定（ユーロ圏向け）

    ECB金利決定は21:15-21:25 JST（冬時間）/ 22:15-22:25 JST（夏時間）に発表

    Args:
        econalpha_id: EconAlpha指標ID
        last_updated_str: 最終更新日時のISO文字列

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

        # マッピングからパターンと国コードを取得
        patterns = get_fmp_event_patterns(econalpha_id)
        if not patterns:
            return False

        country = _get_country_from_mapping(econalpha_id)
        if country is None:
            country = "EU"

        with SessionLocal() as session:
            # 直近の発表イベントをDBから取得
            pattern_conditions = " OR ".join([f"event ILIKE '%{p}%'" for p in patterns])
            query = text(f"""
                SELECT datetime_utc, event, actual
                FROM economic_calendar_events
                WHERE country = :country
                  AND ({pattern_conditions})
                  AND actual IS NOT NULL
                  AND datetime_utc <= NOW()
                ORDER BY datetime_utc DESC
                LIMIT 1
            """)
            row = session.execute(query, {"country": country}).fetchone()

            if not row:
                return False

            dt_utc = row[0]
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=UTC)

            release_datetime = dt_utc.astimezone(JST)

            # 発表時刻より前なら更新不要
            if now < release_datetime:
                return False

            # 更新ウィンドウ
            update_window_end = release_datetime + timedelta(minutes=UPDATE_WINDOW_MINUTES)

            if now <= update_window_end:
                if last_updated < release_datetime:
                    return True
            else:
                if last_updated < release_datetime:
                    return True

            return False

    except Exception as e:
        print(f"Error checking refresh by FMP schedule for {econalpha_id}: {e}")
        return False


def invalidate_next_release_cache(econalpha_id: str) -> bool:
    """
    次回発表日キャッシュを無効化

    Args:
        econalpha_id: EconAlpha指標ID

    Returns:
        成功したかどうか
    """
    cache_key = f"fmp:next_release:{econalpha_id}"
    return redis_client.delete(cache_key)


def get_next_release_by_pattern(
    event_pattern: str,
    use_cache: bool = True,
    country: str = "EU"
) -> Optional[Dict[str, Any]]:
    """
    FMPイベントパターンで次回発表日を取得（econalpha_idを経由しない）

    Args:
        event_pattern: イベント名のパターン（例: "Economic Sentiment"）
        use_cache: Redisキャッシュを使用するか
        country: 国コード（デフォルト: "EU"）

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
                dt_cet = dt_utc.astimezone(CET)
                candidates.append({
                    "date": dt_utc.strftime("%Y-%m-%d"),
                    "datetime_utc": dt_utc.isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
                    "datetime_cet": dt_cet.isoformat(),
                    "time_cet": dt_cet.strftime("%H:%M"),
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
        print(f"Error fetching next release by pattern '{event_pattern}' for country '{country}': {e}")
        return None


def should_refresh_by_pattern(
    event_pattern: str,
    last_updated_str: str,
    country: str = "EU"
) -> bool:
    """
    FMPイベントパターンに基づく更新判定（econalpha_idを経由しない）

    Args:
        event_pattern: イベント名のパターン
        last_updated_str: 最終更新日時のISO文字列
        country: 国コード（デフォルト: "EU"）

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
        print(f"Error checking refresh by pattern '{event_pattern}' for country '{country}': {e}")
        return False
