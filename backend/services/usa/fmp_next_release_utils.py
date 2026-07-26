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


def get_fmp_event_country(econalpha_id: str) -> str:
    """
    indicator_event_mappingから国コードを取得

    Args:
        econalpha_id: EconAlpha指標ID

    Returns:
        国コード。マッピングがなければ'US'（デフォルト）
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
            return "US"

    except Exception as e:
        print(f"Error fetching FMP event country for {econalpha_id}: {e}")
        return "US"


def get_next_release_from_fmp(
    econalpha_id: str,
    patterns: Optional[List[str]] = None,
    use_cache: bool = True,
    country: str = "US",
) -> Optional[Dict[str, Any]]:
    """
    FMP APIから次回発表日を取得

    Args:
        econalpha_id: EconAlpha指標ID（マッピングテーブルから自動取得）
        patterns: FMPイベントパターン（指定しない場合はマッピングテーブルから取得）
        use_cache: Redisキャッシュを使用するか
        country: FMP国コード（デフォルト: "US"）

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
            country=country,
        )

        # 対象イベントを収集
        candidates = []
        for event in events:
            if event.get("country") != country:
                continue

            event_name = event.get("event", "")
            event_name_lower = event_name.lower()

            # パターンマッチング
            # パターンはSQL LIKE形式（%付き）なので、%を除去してマッチング
            matched = False
            for pattern in patterns:
                # SQL LIKE形式の%を除去
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

            # パターンマッチング
            # パターンはSQL LIKE形式（%付き）なので、%を除去してマッチング
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


def _get_last_release_datetime(econalpha_id: str) -> Optional[datetime]:
    """直近（過去）の発表 datetime（JST）を返す。actual有無を問わず最新の過去発表。

    indicator_event_mapping から econalpha_id のパターン・国コードを解決し、
    economic_calendar_events から datetime_utc <= NOW() の最新イベントを取得する。
    ラグガード（resolve_last_updated_after_fetch）が発表時刻の基準として使用する。
    """
    try:
        patterns = get_fmp_event_patterns(econalpha_id)
        if not patterns:
            return None
        country = get_fmp_event_country(econalpha_id)

        from core.database import SessionLocal
        from sqlalchemy import text

        pattern_conditions = " OR ".join(
            [f"event ILIKE :pat{i}" for i in range(len(patterns))]
        )
        pattern_params = {f"pat{i}": f"%{p}%" for i, p in enumerate(patterns)}

        with SessionLocal() as session:
            query = text(f"""
                SELECT datetime_utc
                FROM economic_calendar_events
                WHERE country = :country
                  AND ({pattern_conditions})
                  AND datetime_utc <= NOW()
                ORDER BY datetime_utc DESC
                LIMIT 1
            """)
            row = session.execute(query, {"country": country, **pattern_params}).fetchone()
            if not row:
                return None
            dt_utc = row[0]
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=UTC)
            return dt_utc.astimezone(JST)

    except Exception as e:
        print(f"[FMP Utils] _get_last_release_datetime error for {econalpha_id}: {e}")
        return None


def resolve_last_updated_after_fetch(
    econalpha_id: str,
    new_latest_date: Optional[str],
    prev_latest_date: Optional[str],
    prev_last_updated: Optional[str],
    retry_window_hours: float = 36.0,
) -> str:
    """発表時刻レース対策のラグガード付き last_updated を決定する。

    背景: ダッシュボード再構築はFMP発表時刻に発火するが、一次ソース（FMPカレンダーの
    actual や非FMP API）への新月反映が数秒〜数分遅れることがある。発表時刻ちょうど〜
    直後の取得で旧月をキャッシュし `last_updated=now(≧発表時刻)` を刻むと、
    should_refresh_by_fmp_schedule が「発表消化済み」と判断し次回発表（翌月）まで
    再取得しない（凍結）。実例: 2026-07-01 韓国輸出 Exports YoY(Jun) が 09:00 JST 発表、
    09:00:19 の再構築が actual 未反映の5月をキャッシュし last_updated=09:00:19 を刻んで
    19秒差で凍結した。

    対策: 取得データの最新期間が前回から進んでおらず（=ソース未反映）、かつ直近発表が
    retry_window_hours 以内で、前回キャッシュがその発表をまだ消化していない場合は、
    last_updated を「直近発表時刻の直前」に据え置く。これにより should_refresh が再取得を
    促し続け、ソース反映後の最初のポーリングで新月を取り込める。データが前進した／発表から
    時間が経過した／前回が消化済み の各ケースは now を返す（過剰・無限フェッチを防止）。

    Returns: ISO形式の last_updated 文字列。
    """
    now = datetime.now(JST)
    now_iso = now.isoformat()

    # 比較不能 or データが前進 → 通常どおり now（発表消化）
    if not new_latest_date or not prev_latest_date or new_latest_date > prev_latest_date:
        return now_iso

    # ここに来る = 取得データが前回から前進していない（同一 or 後退）
    last_release = _get_last_release_datetime(econalpha_id)
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
        f"[FMP Utils] lag-guard: source not yet advanced past release "
        f"({last_release.isoformat()}) for {econalpha_id}; holding last_updated to retry "
        f"(latest={new_latest_date})"
    )
    return (last_release - timedelta(seconds=1)).isoformat()


def guarded_last_updated(
    cache_key: str,
    new_latest_date: Optional[str],
    now_str: str,
) -> str:
    """発表レース対策ラグガード（Redisキャッシュ最新月ベースの簡易版）。

    取得データの最新月(new_latest_date)が既存キャッシュの最新月を超えていなければ、
    last_updated を既存キャッシュの旧値のまま維持して返す。発表(例: 8:30 ET)直後～
    一次ソース(FRED/DBnomics等)反映の間に再構築が走ると、ソース未反映のまま旧月を
    last_updated=発表後 で保存し should_refresh が「消化済み」誤判定して次回発表まで
    凍結する。データ未前進なら旧 last_updated を維持し、次回リクエストで再取得して
    新月を自己回復させる（データ自体は既存値の改定反映のため呼び出し側で更新してよい）。

    econalpha_id/発表スケジュールを引かない軽量版。発表時刻の厳密判定が要る場合は
    resolve_last_updated_after_fetch を使う。
    """
    try:
        from core.redis_client import redis_client
        existing_cache = redis_client.get(cache_key)
        existing_latest_date = None
        if existing_cache:
            # (1) トップレベル "latest": {"date": ...} 形式
            lt = existing_cache.get("latest")
            if isinstance(lt, dict):
                existing_latest_date = lt.get("date")
            # (2) "latest" が無い/日付を持たない場合は "data": [...] の末尾要素の date で代替
            if not existing_latest_date:
                data = existing_cache.get("data")
                if isinstance(data, list) and data and isinstance(data[-1], dict):
                    existing_latest_date = data[-1].get("date")
        if existing_latest_date and new_latest_date and new_latest_date <= existing_latest_date:
            return existing_cache.get("last_updated", now_str)
    except Exception as e:
        print(f"[FMP Utils] guarded_last_updated error for {cache_key}: {e}")
    return now_str


def guarded_last_updated_nested(
    cache_key: str,
    series_keys,
    new_latest_date: Optional[str],
    now_str: str,
) -> str:
    """ネスト構造キャッシュ用の発表レース対策ラグガード。

    キャッシュが {series_key: {"data": [...], "latest": {"date": ...}}, ...} 形式
    （mom/yoy、all/common、manufacturing/services 等）の場合に使う。既存キャッシュの
    series_keys のうち最も新しい latest.date を「既存最新月」とみなし、取得データの最新月
    (new_latest_date、呼び出し側で全系列の最大を渡す) がそれを超えていなければ last_updated を
    据え置き、次回リクエストで再取得して新月を自己回復させる。guarded_last_updated の
    ネスト版（トップレベル latest/data を持たないキャッシュ向け）。
    """
    try:
        from core.redis_client import redis_client
        existing_cache = redis_client.get(cache_key)
        existing_latest_date = None
        if isinstance(existing_cache, dict):
            for k in series_keys:
                s = existing_cache.get(k)
                if isinstance(s, dict) and isinstance(s.get("latest"), dict):
                    d = s["latest"].get("date")
                    if d and (existing_latest_date is None or d > existing_latest_date):
                        existing_latest_date = d
        if existing_latest_date and new_latest_date and new_latest_date <= existing_latest_date:
            return existing_cache.get("last_updated", now_str)
    except Exception as e:
        print(f"[FMP Utils] guarded_last_updated_nested error for {cache_key}: {e}")
    return now_str


def guarded_last_updated_keys(
    cache_key: str,
    data_keys,
    new_latest_date: Optional[str],
    now_str: str,
) -> str:
    """トップレベルの data_keys 各々が [{"date": ...}, ...] リストのキャッシュ用ラグガード。

    キャッシュが {"unemployment_rate": [...], "retail_sales_yoy": [...], ...} のように
    トップレベルキー直下にデータリストを持つ形式（ECB/Destatis系に多い、"data"/"latest" を
    持たない）向け。既存キャッシュの data_keys 各リスト末尾要素の date の最大を「既存最新月」と
    みなし、取得データの最新月（new_latest_date、呼び出し側で全リストの最大を渡す）がそれを
    超えていなければ last_updated を据え置く。guarded_last_updated / _nested のキー直下リスト版。
    """
    try:
        from core.redis_client import redis_client
        existing = redis_client.get(cache_key)
        existing_date = None
        if isinstance(existing, dict):
            for k in data_keys:
                v = existing.get(k)
                lst = None
                if isinstance(v, list):
                    lst = v
                elif isinstance(v, dict) and isinstance(v.get("data"), list):
                    # ONS系列コードキー等、値が {"data": [...]} 辞書の場合はその data を見る
                    lst = v["data"]
                if lst and isinstance(lst[-1], dict):
                    d = lst[-1].get("date")
                    if d and (existing_date is None or d > existing_date):
                        existing_date = d
        if existing_date and new_latest_date and new_latest_date <= existing_date:
            return existing.get("last_updated", now_str)
    except Exception as e:
        print(f"[FMP Utils] guarded_last_updated_keys error for {cache_key}: {e}")
    return now_str


def _max_date_of(*lists) -> Optional[str]:
    """複数のデータリスト（[{"date":...}]）から最新 date の最大を返すヘルパー。"""
    cand = []
    for lst in lists:
        if isinstance(lst, list) and lst and isinstance(lst[-1], dict):
            d = lst[-1].get("date")
            if d:
                cand.append(d)
    return max(cand) if cand else None


def should_refresh_by_fmp_schedule(
    econalpha_id: str,
    last_updated_str: str,
    max_age_hours: float = 7 * 24,
) -> bool:
    """
    FMPスケジュールに基づく3分方式の更新判定（DBキャッシュ利用版）

    DBに保存されたイベントスケジュールを使用して判定。
    FMP APIへのリクエストを最小化。

    Args:
        econalpha_id: EconAlpha指標ID
        last_updated_str: 最終更新日時のISO文字列
        max_age_hours: max-ageフォールバックの上限（時間）。これを超えて未更新なら
            発表日判定に関係なく強制リフレッシュ。デフォルト168h(7日)。
            一次ソースが発表当日〜翌日に反映される指標（Cleveland Fed の Median CPI /
            Dallas Fed の Trimmed Mean PCE 等）は24を指定して回復を早める。

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

        # max-age フォールバック（デフォルト7日）:
        # FMP側のイベント欠落・bulk populate の国コード漏れ等で
        # economic_calendar_events に新イベントが入らなくなると、
        # 以下のスケジュール判定は永久に False を返し続け、キャッシュが無期限凍結する
        # （2026-06 KR/TW 凍結の長期化要因）。一定時間で必ずリフレッシュさせ自己回復可能にする。
        # 発表直後はソース(Cleveland/Dallas Fed等)が未反映で、発表日判定が「更新済み」と
        # 誤認して凍結するケース（median_cpi 2026-06）には、呼び出し側で短い max_age_hours
        # （24h等）を指定して当日〜翌日に回復させる。
        if (now - last_updated).total_seconds() > max_age_hours * 60 * 60:
            return True

        # マッピングからパターンと国コードを取得
        patterns = get_fmp_event_patterns(econalpha_id)
        if not patterns:
            # FMPマッピングがない場合、24時間TTLフォールバック
            elapsed = (now - last_updated).total_seconds()
            if elapsed > 24 * 60 * 60:
                return True
            return False

        country = get_fmp_event_country(econalpha_id)

        with SessionLocal() as session:
            # SQLインジェクション対策: 値は直埋めせずバインドパラメータで渡す
            pattern_conditions = " OR ".join(
                [f"event ILIKE :pat{i}" for i in range(len(patterns))]
            )
            pattern_params = {f"pat{i}": f"%{p}%" for i, p in enumerate(patterns)}

            # 1. actual IS NOT NULLの直近イベント（従来の判定）
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
            row = session.execute(query, {"country": country, **pattern_params}).fetchone()

            if row:
                dt_utc = row[0]
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=UTC)

                release_datetime = dt_utc.astimezone(JST)

                if now >= release_datetime and last_updated < release_datetime:
                    return True

            # 2. actual IS NULLだが発表時刻を過ぎたイベントもチェック
            #    FMPがactualを埋めていなくても、FREDやDBには既にデータがある可能性
            #    発表後2時間以内は5分間隔でリフレッシュを繰り返す（FMP actual遅延対策）
            PENDING_GRACE_PERIOD_SECONDS = 2 * 60 * 60  # 2時間
            MIN_RETRY_INTERVAL_SECONDS = 5 * 60          # 5分

            query_pending = text(f"""
                SELECT datetime_utc, event
                FROM economic_calendar_events
                WHERE country = :country
                  AND ({pattern_conditions})
                  AND actual IS NULL
                  AND datetime_utc <= NOW()
                ORDER BY datetime_utc DESC
                LIMIT 1
            """)
            row_pending = session.execute(query_pending, {"country": country, **pattern_params}).fetchone()

            if row_pending:
                dt_utc_pending = row_pending[0]
                if dt_utc_pending.tzinfo is None:
                    dt_utc_pending = dt_utc_pending.replace(tzinfo=UTC)

                pending_release = dt_utc_pending.astimezone(JST)
                elapsed_since_release = (now - pending_release).total_seconds()

                if 0 <= elapsed_since_release <= PENDING_GRACE_PERIOD_SECONDS:
                    # 猶予期間内: last_updatedから5分以上経過していればリフレッシュ
                    elapsed_since_update = (now - last_updated).total_seconds()
                    if elapsed_since_update >= MIN_RETRY_INTERVAL_SECONDS:
                        print(f"[FMP Schedule] Pending release for {econalpha_id}: "
                              f"release={pending_release.strftime('%H:%M')}, "
                              f"elapsed={elapsed_since_release/60:.0f}min, "
                              f"forcing refresh")
                        return True
                else:
                    # 猶予期間外: 従来の判定（last_updatedが発表前なら更新）
                    if now >= pending_release and last_updated < pending_release:
                        return True

            return False

    except Exception as e:
        print(f"Error checking refresh by FMP schedule for {econalpha_id}: {e}")
        return False
