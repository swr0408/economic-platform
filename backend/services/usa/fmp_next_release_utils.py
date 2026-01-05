"""
FMP次回発表日取得ユーティリティ

indicator_event_mappingテーブルのfmp_event_patternsを使用して、
FMP APIから次回発表日を取得する共通関数を提供。

使用方法:
    from services.usa.fmp_next_release_utils import get_next_release_from_fmp, should_refresh_by_fmp

    # 指標IDを指定して次回発表日を取得
    next_release = get_next_release_from_fmp('ism_manufacturing')
    # -> {
    #     'date': '2025-01-03',
    #     'datetime_utc': '2025-01-03T15:00:00+00:00',
    #     'datetime_jst': '2025-01-04T00:00:00+09:00',
    #     'label': 'ISM Manufacturing PMI (Dec)',
    #     'estimate': 48.3
    # }

    # 3分方式での更新判定
    if should_refresh_by_fmp('ism_manufacturing', last_updated_str):
        # データ更新処理
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# キャッシュTTL（1日）
NEXT_RELEASE_CACHE_TTL = 86400

# 発表後の更新チェック期間（分）
UPDATE_WINDOW_MINUTES = 3


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
    use_cache: bool = True
) -> Optional[Dict[str, Any]]:
    """
    FMP APIから次回発表日を取得

    Args:
        econalpha_id: EconAlpha指標ID（マッピングテーブルから自動取得）
        patterns: FMPイベントパターン（指定しない場合はマッピングテーブルから取得）
        use_cache: Redisキャッシュを使用するか

    Returns:
        次回発表日情報:
        {
            'date': 'YYYY-MM-DD',
            'datetime_utc': 'ISO形式',
            'label': 'イベント名',
            'estimate': 予測値 or None
        }
        取得できなければNone
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

    try:
        from services.calendar.fmp_service import fmp_service

        today = date.today()
        # 60日先までのイベントを取得
        events = fmp_service.fetch_calendar(
            today,
            today + timedelta(days=60),
            country="US"
        )

        # 対象イベントを収集
        candidates = []
        for event in events:
            if event.get("country") != "US":
                continue

            event_name = event.get("event", "")
            event_name_lower = event_name.lower()

            # パターンマッチング
            matched = False
            for pattern in patterns:
                if pattern.lower() in event_name_lower:
                    matched = True
                    break

            if not matched:
                continue

            # 将来のイベント（actual が None）のみ
            if event.get("actual") is not None:
                continue

            dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
            if dt_utc and dt_utc.date() >= today:
                # UTCからJSTに変換
                dt_jst = dt_utc.astimezone(JST)
                candidates.append({
                    "date": dt_utc.strftime("%Y-%m-%d"),
                    "datetime_utc": dt_utc.isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
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


def get_next_releases_batch(
    econalpha_ids: List[str],
    use_cache: bool = True
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    複数指標の次回発表日を一括取得

    Args:
        econalpha_ids: EconAlpha指標IDのリスト
        use_cache: Redisキャッシュを使用するか

    Returns:
        指標ID -> 次回発表日情報のマップ
    """
    result = {}

    for econalpha_id in econalpha_ids:
        result[econalpha_id] = get_next_release_from_fmp(econalpha_id, use_cache=use_cache)

    return result


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


def get_last_release_from_fmp(
    econalpha_id: str,
    patterns: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    FMP APIから直近の発表日時を取得（過去のイベント）

    Args:
        econalpha_id: EconAlpha指標ID
        patterns: FMPイベントパターン

    Returns:
        直近の発表日時情報
    """
    if patterns is None:
        patterns = get_fmp_event_patterns(econalpha_id)

    if not patterns:
        return None

    try:
        from services.calendar.fmp_service import fmp_service

        today = date.today()
        # 過去60日分を取得
        events = fmp_service.fetch_calendar(
            today - timedelta(days=60),
            today,
            country="US"
        )

        candidates = []
        for event in events:
            if event.get("country") != "US":
                continue

            event_name = event.get("event", "")
            event_name_lower = event_name.lower()

            matched = False
            for pattern in patterns:
                if pattern.lower() in event_name_lower:
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
                candidates.append({
                    "date": dt_utc.strftime("%Y-%m-%d"),
                    "datetime_utc": dt_utc.isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
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


def should_refresh_by_fmp(
    econalpha_id: str,
    last_updated_str: str,
    patterns: Optional[List[str]] = None,
) -> bool:
    """
    FMPの発表日時に基づいて、3分方式でキャッシュ更新が必要かを判定

    判定ロジック:
    1. 直近の発表日時を取得
    2. 現在時刻が発表日時を過ぎているか確認
    3. 発表日時から3分以内なら、最終更新が発表日時より前なら更新
    4. 発表日時を3分以上過ぎていて、まだ更新していなければ更新

    Args:
        econalpha_id: EconAlpha指標ID
        last_updated_str: 最終更新日時のISO文字列
        patterns: FMPイベントパターン（指定しない場合はマッピングから取得）

    Returns:
        True: 更新が必要
        False: キャッシュ有効
    """
    try:
        # 最終更新日時をパース
        last_updated = datetime.fromisoformat(last_updated_str)
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=JST)

        now = datetime.now(JST)

        # 直近の発表日時を取得（キャッシュから）
        # 注: ここでは過去の発表イベントではなく、直近の発表時刻を使う
        # FMPの過去イベントを使用
        last_release_info = get_last_release_from_fmp(econalpha_id, patterns)

        if not last_release_info:
            return False

        # 発表日時をパース
        release_datetime_str = last_release_info.get("datetime_jst")
        if not release_datetime_str:
            return False

        release_datetime = datetime.fromisoformat(release_datetime_str)

        # 発表時刻より前なら更新不要
        if now < release_datetime:
            return False

        # 発表時刻から3分以内かどうか
        update_window_end = release_datetime + timedelta(minutes=UPDATE_WINDOW_MINUTES)
        in_update_window = now <= update_window_end

        if in_update_window:
            # 3分以内: 最終更新が発表時刻より前なら更新
            if last_updated < release_datetime:
                return True
        else:
            # 3分経過後: 発表時刻以降に更新していなければ更新
            if last_updated < release_datetime:
                return True

        return False

    except Exception as e:
        print(f"Error checking refresh status for {econalpha_id}: {e}")
        return False


def should_refresh_by_fmp_schedule(
    econalpha_id: str,
    last_updated_str: str,
) -> bool:
    """
    FMPスケジュールに基づく3分方式の更新判定（DBキャッシュ利用版）

    DBに保存されたイベントスケジュールを使用して判定。
    FMP APIへのリクエストを最小化。

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

        # マッピングからパターンを取得
        patterns = get_fmp_event_patterns(econalpha_id)
        if not patterns:
            return False

        with SessionLocal() as session:
            # 直近の発表イベントをDBから取得
            # actual IS NOT NULLで過去のイベントのみ
            pattern_conditions = " OR ".join([f"event ILIKE '%{p}%'" for p in patterns])
            query = text(f"""
                SELECT datetime_utc, event, actual
                FROM economic_calendar_events
                WHERE country = 'US'
                  AND ({pattern_conditions})
                  AND actual IS NOT NULL
                  AND datetime_utc <= NOW()
                ORDER BY datetime_utc DESC
                LIMIT 1
            """)
            row = session.execute(query).fetchone()

            if not row:
                return False

            dt_utc = row[0]
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=UTC)

            release_datetime = dt_utc.astimezone(JST)

            # 発表時刻より前なら更新不要
            if now < release_datetime:
                return False

            # 3分方式での判定
            update_window_end = release_datetime + timedelta(minutes=UPDATE_WINDOW_MINUTES)

            if now <= update_window_end:
                # 3分以内
                if last_updated < release_datetime:
                    return True
            else:
                # 3分経過後
                if last_updated < release_datetime:
                    return True

            return False

    except Exception as e:
        print(f"Error checking refresh by FMP schedule for {econalpha_id}: {e}")
        return False
