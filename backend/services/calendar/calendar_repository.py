"""
経済カレンダー リポジトリ

PostgreSQLへのCRUD操作を提供
"""
import json
from datetime import date, datetime
from typing import Any, Optional

try:
    from core.database import get_db_connection
except ImportError:
    from backend.core.database import get_db_connection


class CalendarRepository:
    """経済カレンダーのDB操作"""

    # =========================================================================
    # イベント操作
    # =========================================================================

    def upsert_events(self, events: list[dict]) -> int:
        """
        イベントを一括Upsert

        Args:
            events: 処理済みイベントリスト

        Returns:
            Upsertしたレコード数
        """
        if not events:
            return 0

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                count = 0
                for event in events:
                    try:
                        cur.execute("""
                            INSERT INTO economic_calendar_events (
                                provider, event_key, country, currency, event, event_period,
                                datetime_raw, datetime_utc, has_time, impact,
                                previous, estimate, actual, change, change_pct, unit, raw_json
                            ) VALUES (
                                %(provider)s, %(event_key)s, %(country)s, %(currency)s, %(event)s, %(event_period)s,
                                %(datetime_raw)s, %(datetime_utc)s, %(has_time)s, %(impact)s,
                                %(previous)s, %(estimate)s, %(actual)s, %(change)s, %(change_pct)s, %(unit)s, %(raw_json)s
                            )
                            ON CONFLICT (provider, event_key) DO UPDATE SET
                                previous = EXCLUDED.previous,
                                estimate = EXCLUDED.estimate,
                                actual = EXCLUDED.actual,
                                change = EXCLUDED.change,
                                change_pct = EXCLUDED.change_pct,
                                impact = EXCLUDED.impact,
                                raw_json = EXCLUDED.raw_json,
                                updated_at = NOW()
                        """, {
                            **event,
                            "raw_json": json.dumps(event["raw_json"]),
                        })
                        count += 1
                    except Exception as e:
                        print(f"[CalendarRepo] Error upserting event: {e}")
                        continue

                conn.commit()
                return count

    def get_events_by_country(
        self,
        country: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 1000
    ) -> list[dict]:
        """国別のイベントを取得"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT id, provider, country, currency, event, event_period,
                           datetime_raw, datetime_utc, has_time, impact,
                           previous, estimate, actual, change, change_pct, unit, ingested_at
                    FROM economic_calendar_events
                    WHERE country = %s
                """
                params = [country]

                if from_date:
                    query += " AND datetime_utc >= %s"
                    params.append(from_date)
                if to_date:
                    query += " AND datetime_utc <= %s"
                    params.append(to_date)

                query += " ORDER BY datetime_utc DESC LIMIT %s"
                params.append(limit)

                cur.execute(query, params)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_events_by_econalpha_id(  # noqa: C901
        self,
        econalpha_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 100
    ) -> list[dict]:
        """
        EconAlpha指標IDに紐づくイベントを取得

        マッピングテーブルのfmp_event_patternsを使用
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # まずマッピングを取得
                cur.execute("""
                    SELECT country, fmp_event_patterns
                    FROM indicator_event_mapping
                    WHERE econalpha_id = %s AND is_active = TRUE
                """, (econalpha_id,))
                mapping = cur.fetchone()

                if not mapping:
                    return []

                country, patterns = mapping

                # パターンにマッチするイベントを検索
                # イベント名から期間情報を除いたものでLIKE検索
                conditions = []
                params = [country]

                for pattern in patterns:
                    conditions.append("event LIKE %s")
                    params.append(f"{pattern}%")

                if not conditions:
                    return []

                # DISTINCT ON で同一日時の重複を除外（impact順で最も重要なものを優先）
                query = f"""
                    SELECT DISTINCT ON (datetime_utc)
                           id, provider, country, currency, event, event_period,
                           datetime_raw, datetime_utc, has_time, impact,
                           previous, estimate, actual, change, change_pct, unit
                    FROM economic_calendar_events
                    WHERE country = %s AND ({' OR '.join(conditions)})
                """

                if from_date:
                    query += " AND datetime_utc >= %s"
                    params.append(from_date)
                if to_date:
                    query += " AND datetime_utc <= %s"
                    params.append(to_date)

                # DISTINCT ON用: datetime_utcが最初、次にimpact優先度
                # これにより同一日時で最も重要なイベントが選択される
                query += """ ORDER BY datetime_utc DESC,
                             CASE impact
                                 WHEN 'High' THEN 1
                                 WHEN 'Medium' THEN 2
                                 WHEN 'Low' THEN 3
                                 ELSE 4
                             END ASC
                             LIMIT %s"""
                params.append(limit)

                cur.execute(query, params)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]

    # =========================================================================
    # 同期状態
    # =========================================================================

    def update_sync_state(
        self,
        provider: str,
        from_date: date,
        to_date: date,
        records_count: int,
        error: Optional[str] = None
    ):
        """同期状態を更新"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO provider_sync_state (
                        provider, last_success_at, last_range_from, last_range_to,
                        records_count, last_error
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider) DO UPDATE SET
                        last_success_at = CASE WHEN EXCLUDED.last_error IS NULL THEN NOW() ELSE provider_sync_state.last_success_at END,
                        last_range_from = EXCLUDED.last_range_from,
                        last_range_to = EXCLUDED.last_range_to,
                        records_count = EXCLUDED.records_count,
                        last_error = EXCLUDED.last_error,
                        updated_at = NOW()
                """, (
                    provider,
                    datetime.utcnow() if not error else None,
                    from_date,
                    to_date,
                    records_count,
                    error,
                ))
                conn.commit()

    def get_sync_state(self, provider: str) -> Optional[dict]:
        """同期状態を取得"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT provider, last_success_at, last_range_from, last_range_to,
                           records_count, last_error, updated_at
                    FROM provider_sync_state
                    WHERE provider = %s
                """, (provider,))
                row = cur.fetchone()
                if row:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
                return None

    # =========================================================================
    # 指標候補
    # =========================================================================

    def refresh_indicator_candidates(self, provider: str = "FMP"):
        """
        過去1年のイベントから指標候補を再集計

        集計SQL実行
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(r"""
                    WITH base AS (
                        SELECT
                            provider,
                            country,
                            event,
                            lower(regexp_replace(
                                regexp_replace(trim(event), '\s*\([^)]*\)\s*$', '', 'g'),
                                '\s+', ' ', 'g'
                            )) AS event_norm,
                            datetime_utc,
                            has_time
                        FROM economic_calendar_events
                        WHERE provider = %s
                          AND datetime_utc >= (NOW() - INTERVAL '365 days')
                    )
                    INSERT INTO economic_indicator_candidates AS c
                    (
                        provider, country, event, event_norm,
                        occurrences_1y, first_seen_utc, last_seen_utc, has_time_ratio
                    )
                    SELECT
                        provider,
                        country,
                        MAX(event) AS event,
                        event_norm,
                        COUNT(*) AS occurrences_1y,
                        MIN(datetime_utc),
                        MAX(datetime_utc),
                        (SUM(CASE WHEN has_time THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100
                    FROM base
                    WHERE country IN ('US', 'JP', 'EU', 'DE', 'GB', 'CA', 'AU', 'CN', 'CH', 'NZ', 'FR')
                    GROUP BY provider, country, event_norm
                    ON CONFLICT (provider, country, event_norm)
                    DO UPDATE SET
                        event = EXCLUDED.event,
                        occurrences_1y = EXCLUDED.occurrences_1y,
                        first_seen_utc = EXCLUDED.first_seen_utc,
                        last_seen_utc = EXCLUDED.last_seen_utc,
                        has_time_ratio = EXCLUDED.has_time_ratio,
                        updated_at = NOW()
                """, (provider,))
                conn.commit()
                print(f"[CalendarRepo] Refreshed indicator candidates for {provider}")

    def get_indicator_candidates(
        self,
        country: Optional[str] = None,
        min_occurrences: int = 1
    ) -> list[dict]:
        """指標候補一覧を取得"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT id, provider, country, event, event_norm,
                           occurrences_1y, first_seen_utc, last_seen_utc, has_time_ratio
                    FROM economic_indicator_candidates
                    WHERE occurrences_1y >= %s
                """
                params = [min_occurrences]

                if country:
                    query += " AND country = %s"
                    params.append(country)

                query += " ORDER BY country, occurrences_1y DESC"

                cur.execute(query, params)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]

    # =========================================================================
    # マッピング操作
    # =========================================================================

    def get_mapping_by_econalpha_id(self, econalpha_id: str) -> Optional[dict]:
        """EconAlpha IDでマッピングを取得"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, econalpha_id, econalpha_name, country, frequency,
                           fmp_event_patterns, is_active
                    FROM indicator_event_mapping
                    WHERE econalpha_id = %s
                """, (econalpha_id,))
                row = cur.fetchone()
                if row:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
                return None

    def get_all_mappings(self, country: Optional[str] = None) -> list[dict]:
        """全マッピングを取得"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT id, econalpha_id, econalpha_name, country, frequency,
                           fmp_event_patterns, is_active
                    FROM indicator_event_mapping
                    WHERE is_active = TRUE
                """
                params = []

                if country:
                    query += " AND country = %s"
                    params.append(country)

                query += " ORDER BY country, econalpha_name"

                cur.execute(query, params)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]

    # =========================================================================
    # 指標発表履歴
    # =========================================================================

    def sync_indicator_releases(self, econalpha_id: str) -> int:
        """
        指標発表履歴を同期

        economic_calendar_eventsからindicator_releasesへコピー
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # マッピング取得
                cur.execute("""
                    SELECT country, fmp_event_patterns
                    FROM indicator_event_mapping
                    WHERE econalpha_id = %s AND is_active = TRUE
                """, (econalpha_id,))
                mapping = cur.fetchone()

                if not mapping:
                    return 0

                country, patterns = mapping

                # パターンマッチ条件を作成
                conditions = []
                params = [country]
                for pattern in patterns:
                    conditions.append("e.event LIKE %s")
                    params.append(f"{pattern}%")

                if not conditions:
                    return 0

                # Upsert
                cur.execute(f"""
                    INSERT INTO indicator_releases (
                        econalpha_id, release_datetime, release_date, period_label,
                        previous, estimate, actual, surprise, surprise_pct, impact, source_event_id
                    )
                    SELECT
                        %s,
                        e.datetime_utc,
                        e.datetime_utc::DATE,
                        e.event_period,
                        e.previous,
                        e.estimate,
                        e.actual,
                        CASE WHEN e.actual IS NOT NULL AND e.estimate IS NOT NULL
                             THEN e.actual - e.estimate ELSE NULL END,
                        CASE WHEN e.actual IS NOT NULL AND e.estimate IS NOT NULL AND e.estimate != 0
                             THEN ((e.actual - e.estimate) / ABS(e.estimate)) * 100 ELSE NULL END,
                        e.impact,
                        e.id
                    FROM economic_calendar_events e
                    WHERE e.country = %s AND ({' OR '.join(conditions)})
                      AND e.datetime_utc IS NOT NULL
                    ON CONFLICT (econalpha_id, release_datetime) DO UPDATE SET
                        previous = EXCLUDED.previous,
                        estimate = EXCLUDED.estimate,
                        actual = EXCLUDED.actual,
                        surprise = EXCLUDED.surprise,
                        surprise_pct = EXCLUDED.surprise_pct,
                        impact = EXCLUDED.impact
                """, (econalpha_id, *params))

                count = cur.rowcount
                conn.commit()
                return count

    def get_indicator_releases(
        self,
        econalpha_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 100
    ) -> list[dict]:
        """指標発表履歴を取得"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT id, econalpha_id, release_datetime, release_date, period_label,
                           previous, estimate, actual, surprise, surprise_pct, impact
                    FROM indicator_releases
                    WHERE econalpha_id = %s
                """
                params = [econalpha_id]

                if from_date:
                    query += " AND release_date >= %s"
                    params.append(from_date)
                if to_date:
                    query += " AND release_date <= %s"
                    params.append(to_date)

                query += " ORDER BY release_datetime DESC LIMIT %s"
                params.append(limit)

                cur.execute(query, params)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]


# シングルトンインスタンス
calendar_repository = CalendarRepository()
