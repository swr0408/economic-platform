"""
FMP次回発表日取得ユーティリティ（カナダ向け）

indicator_event_mappingテーブルのfmp_event_patternsを使用して、
FMP APIから次回発表日を取得する共通関数を提供。

使用方法:
    from services.canada.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern

    # パターンを指定して次回発表日を取得
    next_release = get_next_release_by_pattern('BoC Interest Rate Decision', country='CA')
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

# タイムゾーン
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")
JST = ZoneInfo("Asia/Tokyo")

# キャッシュTTL（1日）
NEXT_RELEASE_CACHE_TTL = 86400

# 発表後の更新チェック期間（分）
# BOC金利決定は09:45 トロント時間（EST/EDT）に発表
UPDATE_WINDOW_MINUTES = 10


def get_next_release_by_pattern(
    event_pattern: str,
    use_cache: bool = True,
    country: str = "CA"
) -> Optional[Dict[str, Any]]:
    """
    FMPイベントパターンで次回発表日を取得

    まずDBのeconomic_calendar_eventsテーブルから検索し、
    なければFMP APIを呼び出す。

    Args:
        event_pattern: イベント名のパターン（例: "BoC Interest Rate Decision"）
        use_cache: Redisキャッシュを使用するか
        country: 国コード（デフォルト: "CA"）

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
                dt_toronto = dt_utc.astimezone(TORONTO)
                candidates.append({
                    "date": dt_utc.strftime("%Y-%m-%d"),
                    "datetime_utc": dt_utc.isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
                    "datetime_toronto": dt_toronto.isoformat(),
                    "time_toronto": dt_toronto.strftime("%H:%M"),
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
        print(f"[CA FMP Utils] Error fetching next release by pattern '{event_pattern}' for country '{country}': {e}")
        return None


def _get_next_release_from_db(
    event_pattern: str,
    country: str = "CA"
) -> Optional[Dict[str, Any]]:
    """
    DBのeconomic_calendar_eventsテーブルから次回発表日を取得

    Args:
        event_pattern: イベント名のパターン
        country: 国コード

    Returns:
        次回発表日情報、なければNone
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
            dt_toronto = dt_utc.astimezone(TORONTO)

            return {
                "date": dt_utc.strftime("%Y-%m-%d"),
                "datetime_utc": dt_utc.isoformat(),
                "datetime_jst": dt_jst.isoformat(),
                "time_jst": dt_jst.strftime("%H:%M"),
                "datetime_toronto": dt_toronto.isoformat(),
                "time_toronto": dt_toronto.strftime("%H:%M"),
                "label": event_name,
                "estimate": float(estimate) if estimate is not None else None,
            }

    except Exception as e:
        print(f"[CA FMP Utils] Error fetching from DB: {e}")
        return None


def should_refresh_by_pattern(
    event_pattern: str,
    last_updated_str: str,
    country: str = "CA"
) -> bool:
    """
    FMPイベントパターンに基づく更新判定

    Args:
        event_pattern: イベント名のパターン
        last_updated_str: 最終更新日時のISO文字列
        country: 国コード（デフォルト: "CA"）

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
        print(f"[CA FMP Utils] Error checking refresh by pattern '{event_pattern}' for country '{country}': {e}")
        return False


def invalidate_next_release_cache(event_pattern: str, country: str = "CA") -> bool:
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


def _get_last_release_datetime(event_patterns, country: str = "CA") -> Optional[datetime]:
    """直近（過去）の発表 datetime（JST）を返す。actual有無を問わず最新の過去発表。

    複数パターンを渡した場合は最も新しい発表時刻を採用する。
    """
    if isinstance(event_patterns, str):
        event_patterns = [event_patterns]
    try:
        from core.database import SessionLocal
        from sqlalchemy import text, bindparam

        valid_countries = [country]
        best = None
        with SessionLocal() as session:
            for pattern in event_patterns:
                query = text("""
                    SELECT datetime_utc
                    FROM economic_calendar_events
                    WHERE country IN :countries
                      AND event ILIKE :pattern
                      AND datetime_utc <= NOW()
                    ORDER BY datetime_utc DESC
                    LIMIT 1
                """).bindparams(bindparam("countries", expanding=True))
                row = session.execute(
                    query, {"countries": valid_countries, "pattern": f"%{pattern}%"}
                ).fetchone()
                if row:
                    dt_utc = row[0]
                    if dt_utc.tzinfo is None:
                        dt_utc = dt_utc.replace(tzinfo=UTC)
                    dt_jst = dt_utc.astimezone(JST)
                    if best is None or dt_jst > best:
                        best = dt_jst
        return best
    except Exception as e:
        print(f"[CA FMP Utils] _get_last_release_datetime error: {e}")
        return None


def resolve_last_updated_after_fetch(
    event_patterns,
    new_latest_date: Optional[str],
    prev_latest_date: Optional[str],
    prev_last_updated: Optional[str],
    country: str = "CA",
    retry_window_hours: float = 36.0,
) -> str:
    """発表時刻レース対策のラグガード付き last_updated を決定する。

    背景: ダッシュボード更新はFMP発表時刻（=StatCan公式発表時刻 08:30 ET）に発火するが、
    StatCanのCSV一括zip（18100004-eng.zip等）への新月反映が数分遅れることがある。発表時刻
    ちょうど〜直後の取得で旧月をキャッシュし `last_updated=now(≧発表時刻)` を刻むと
    should_refresh_by_pattern が「発表消化済み」と判断し、次回発表（翌月）まで再取得しない
    （凍結）。WDS APIは発表時刻に即更新されるためサービス間で取りこぼし差が出る（2026-06-22
    ca_cpi がApril凍結／ca_cpi_service_rent はMay取得の不整合が発生）。

    対策: 取得データの最新期間が前回から進んでおらず（=ソース未反映）、かつ直近発表が
    retry_window_hours 以内で、前回キャッシュがその発表をまだ消化していない場合は、
    last_updated を「直近発表時刻の直前」に据え置く。これにより should_refresh_by_pattern
    が再取得を促し続け、StatCan反映後の最初のポーリングで新月を取り込める。
    データが前進した／発表から時間が経過した／前回が消化済み の各ケースは now を返す
    （過剰フェッチ・無限フェッチを防止）。

    Returns: ISO形式の last_updated 文字列。
    """
    now = datetime.now(JST)
    now_iso = now.isoformat()

    # 比較不能 or データが前進 → 通常どおり now（発表消化）
    if not new_latest_date or not prev_latest_date or new_latest_date > prev_latest_date:
        return now_iso

    # ここに来る = 取得データが前回から前進していない（同一 or 後退）
    last_release = _get_last_release_datetime(event_patterns, country)
    if not last_release or now < last_release:
        return now_iso

    # 発表から時間が経過しすぎ → 据え置かない（無限フェッチ防止）
    age_hours = (now - last_release).total_seconds() / 3600.0
    if age_hours > retry_window_hours:
        return now_iso

    # 前回キャッシュが既にこの発表を消化済み（last_updated≧発表）なら据え置かない
    if prev_last_updated:
        try:
            plu = datetime.fromisoformat(prev_last_updated)
            if plu.tzinfo is None:
                plu = plu.replace(tzinfo=JST)
            if plu >= last_release:
                return now_iso
        except Exception:
            pass

    # 発表直後だがソース未反映 → 消化扱いにせず、発表直前に据え置いて再取得を促す
    print(
        f"[CA FMP Utils] lag-guard: source not yet advanced past release "
        f"({last_release.isoformat()}); holding last_updated to retry "
        f"(latest={new_latest_date})"
    )
    return (last_release - timedelta(seconds=1)).isoformat()
