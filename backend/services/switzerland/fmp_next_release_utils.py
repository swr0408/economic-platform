"""
FMP次回発表日取得ユーティリティ（スイス向け）

indicator_event_mappingテーブルのfmp_event_patternsを使用して、
FMP APIから次回発表日を取得する共通関数を提供。

使用方法:
    from services.switzerland.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern

    # パターンを指定して次回発表日を取得
    next_release = get_next_release_by_pattern('SNB Interest Rate Decision', country='CH')
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

# タイムゾーン
ZURICH = ZoneInfo("Europe/Zurich")
UTC = ZoneInfo("UTC")
JST = ZoneInfo("Asia/Tokyo")

# キャッシュTTL（1日）
NEXT_RELEASE_CACHE_TTL = 86400

# 発表後の更新チェック期間（分）
# SNB金利決定は08:30 チューリッヒ時間に発表
UPDATE_WINDOW_MINUTES = 10

# FMPイベントパターン → SNB ICSカレンダーのカテゴリ対応表
# SNB ICSには金融政策関連のイベントしか含まれないため、ここに載るのは限定的。
# CPI/雇用/PPI等の経済指標は SNB ICS に存在しないので追加してはいけない。
_SNB_ICS_PATTERN_TO_CATEGORY = {
    "SNB Interest Rate Decision": "monetary_policy_decision",
}


def get_next_release_by_pattern(
    event_pattern: str,
    use_cache: bool = True,
    country: str = "CH"
) -> Optional[Dict[str, Any]]:
    """
    FMPイベントパターンで次回発表日を取得

    まずDBのeconomic_calendar_eventsテーブルから検索し、
    なければFMP APIを呼び出す。

    Args:
        event_pattern: イベント名のパターン（例: "SNB Interest Rate Decision"）
        use_cache: Redisキャッシュを使用するか
        country: 国コード（デフォルト: "CH"）

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
                dt_zurich = dt_utc.astimezone(ZURICH)
                candidates.append({
                    "date": dt_utc.strftime("%Y-%m-%d"),
                    "datetime_utc": dt_utc.isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
                    "datetime_zurich": dt_zurich.isoformat(),
                    "time_zurich": dt_zurich.strftime("%H:%M"),
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
        print(f"[CH FMP Utils] Error fetching next release by pattern '{event_pattern}' for country '{country}': {e}")
        return None


def _get_next_release_from_db(
    event_pattern: str,
    country: str = "CH"
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
            dt_zurich = dt_utc.astimezone(ZURICH)

            return {
                "date": dt_utc.strftime("%Y-%m-%d"),
                "datetime_utc": dt_utc.isoformat(),
                "datetime_jst": dt_jst.isoformat(),
                "time_jst": dt_jst.strftime("%H:%M"),
                "datetime_zurich": dt_zurich.isoformat(),
                "time_zurich": dt_zurich.strftime("%H:%M"),
                "label": event_name,
                "estimate": float(estimate) if estimate is not None else None,
            }

    except Exception as e:
        print(f"[CH FMP Utils] Error fetching from DB: {e}")
        return None


def _get_latest_past_release_from_snb_ics(
    event_pattern: str,
    now: datetime,
) -> Optional[datetime]:
    """
    SNB ICSカレンダーから event_pattern に対応する直近の過去発表日時を取得。

    FMP DB が空・古い場合の2次フォールバック。SNB ICSは年初に通年の予定が公開されるため、
    FMP backfill 停止中でも金融政策決定の最新発表を検出できる。

    Returns:
        JSTタイムゾーン付きdatetime、または None（パターンが未マッピング/ICSに該当イベントなし）
    """
    category = _SNB_ICS_PATTERN_TO_CATEGORY.get(event_pattern)
    if category is None:
        return None

    try:
        from services.switzerland.snb_calendar_service import snb_calendar_service

        schedule = snb_calendar_service._get_schedule() or {}
        events = schedule.get(category, [])

        latest_jst: Optional[datetime] = None
        for event in events:
            dt_str = event.get("datetime")
            if not dt_str:
                continue
            try:
                event_dt_zurich = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=ZURICH)
            except ValueError:
                continue
            event_dt_jst = event_dt_zurich.astimezone(JST)
            if event_dt_jst > now:
                continue
            if latest_jst is None or event_dt_jst > latest_jst:
                latest_jst = event_dt_jst

        return latest_jst

    except Exception as e:
        print(f"[CH FMP Utils] Error reading SNB ICS for pattern '{event_pattern}': {e}")
        return None


def should_refresh_by_pattern(
    event_pattern: str,
    last_updated_str: str,
    country: str = "CH",
    max_age_hours: float = 168.0,
) -> bool:
    """
    FMPイベントパターンに基づく更新判定

    Args:
        event_pattern: イベント名のパターン
        last_updated_str: 最終更新日時のISO文字列
        country: 国コード（デフォルト: "CH"）
        max_age_hours: TTLフォールバック上限（時間）。FMPカレンダー/ICSに発表が
            無い・古い場合でも、この時間を超えたら再取得して永久凍結を防ぐ。
            デフォルト168h=7日。0以下で無効化。

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

        # 3. SNB ICSカレンダーにフォールバック
        # FMPバックフィルが遅延/停止していてもSNB発表（金融政策決定）に対応するため。
        # 対象は SNB ICS に存在するパターンのみ（金融政策発表系）。
        ics_release_dt = _get_latest_past_release_from_snb_ics(event_pattern, now)
        if ics_release_dt and last_updated < ics_release_dt <= now:
            return True

        # 4. TTLフォールバック（多層防御）
        #    FMP/ICSに発表が欠落/停止していても、一定時間を超えたら必ず再取得する。
        #    UK版と異なりCH版には従来TTLが無く、発表時刻レースで消化扱いになると
        #    次回会合（四半期後）まで凍結する穴があったため追加。
        if max_age_hours and max_age_hours > 0:
            age_hours = (now - last_updated).total_seconds() / 3600.0
            if age_hours >= max_age_hours:
                print(
                    f"[CH FMP Utils] TTL fallback triggered for '{event_pattern}' "
                    f"(age {age_hours:.1f}h >= {max_age_hours}h)"
                )
                return True

        return False

    except Exception as e:
        print(f"[CH FMP Utils] Error checking refresh by pattern '{event_pattern}' for country '{country}': {e}")
        return False


def _get_last_release_datetime(event_pattern: str, country: str = "CH"):
    """直近（過去）の発表 datetime（JST）を返す。actual有無を問わず最新の過去発表。

    DB（economic_calendar_events、datetime_utc<=NOW）とSNB ICSカレンダーの双方を見て
    最も新しい過去発表時刻を採用する（FMP actual未populate中でも発表時刻を捕捉するため）。
    """
    now = datetime.now(JST)
    best = None
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            query = text("""
                SELECT datetime_utc
                FROM economic_calendar_events
                WHERE country = :country
                  AND event ILIKE :pattern
                  AND datetime_utc <= NOW()
                ORDER BY datetime_utc DESC
                LIMIT 1
            """)
            row = session.execute(
                query, {"country": country, "pattern": f"%{event_pattern}%"}
            ).fetchone()
            if row and row[0]:
                dt_utc = row[0]
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=UTC)
                best = dt_utc.astimezone(JST)
    except Exception as e:
        print(f"[CH FMP Utils] _get_last_release_datetime DB error: {e}")

    # SNB ICS フォールバック（DBが空/古い場合の補完）
    ics_dt = _get_latest_past_release_from_snb_ics(event_pattern, now)
    if ics_dt and (best is None or ics_dt > best):
        best = ics_dt

    return best


def resolve_last_updated_after_fetch(
    event_pattern: str,
    new_latest_date: Optional[str],
    prev_latest_date: Optional[str],
    prev_last_updated: Optional[str],
    country: str = "CH",
    retry_window_hours: float = 36.0,
) -> str:
    """発表時刻レース対策のラグガード付き last_updated を決定する。

    背景: ダッシュボード更新はFMP発表時刻（=SNB発表時刻）に発火するが、FMPの actual
    取り込みやSNBプレスリリース画像の公開は発表時刻より遅れることがある。発表時刻
    ちょうどの取得で旧分をキャッシュし `last_updated=now(≧発表時刻)` を刻むと
    should_refresh が「発表消化済み」と判断し、次回発表（四半期後）/TTLまで再取得しない。

    対策: 取得データの最新（発表日）が前回から進んでおらず（=ソース未反映）、かつ直近発表が
    retry_window_hours 以内で、前回キャッシュがその発表をまだ消化していない場合は、
    last_updated を「直近発表時刻の直前」に据え置く。これにより should_refresh_by_pattern が
    再取得を促し続け、FMP actual反映/SNB画像公開後の最初のポーリングで新分を取り込める。
    データが前進した／発表から時間が経過した／前回が消化済み の各ケースは now を返す。

    Returns: ISO形式の last_updated 文字列。
    """
    now = datetime.now(JST)
    now_iso = now.isoformat()

    # 比較不能 or データが前進 → 通常どおり now（発表消化）
    if not new_latest_date or not prev_latest_date or new_latest_date > prev_latest_date:
        return now_iso

    # ここに来る = 取得データ（発表日）が前回から前進していない
    last_release = _get_last_release_datetime(event_pattern, country)
    if not last_release or now < last_release:
        return now_iso

    # 発表から時間が経過しすぎ → 据え置かない（無限フェッチ防止。以後はTTLが backstop）
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

    print(
        f"[CH FMP Utils] lag-guard: source not yet advanced past release "
        f"({last_release.isoformat()}); holding last_updated to retry "
        f"(latest={new_latest_date})"
    )
    return (last_release - timedelta(seconds=1)).isoformat()


def invalidate_next_release_cache(event_pattern: str, country: str = "CH") -> bool:
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
