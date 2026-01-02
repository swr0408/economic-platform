"""
市場データリポジトリ
PostgreSQL + TimescaleDB へのCRUD操作
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import SessionLocal


class MarketRepository:
    """市場データのDB操作"""

    def __init__(self, session: Optional[Session] = None):
        self._session = session
        self._own_session = session is None

    def _get_session(self) -> Session:
        if self._session:
            return self._session
        return SessionLocal()

    def _close_session(self, session: Session):
        if self._own_session:
            session.close()

    # =========================================================================
    # 銘柄マスタ
    # =========================================================================

    def get_symbol(self, symbol_id: str) -> Optional[Dict[str, Any]]:
        """銘柄情報を取得"""
        session = self._get_session()
        try:
            result = session.execute(
                text("""
                    SELECT id, ticker, name, name_en, category, sub_category,
                           is_active, is_calculated, base_symbol_id, fx_symbol_id, operation
                    FROM public.market_symbols
                    WHERE id = :symbol_id
                """),
                {"symbol_id": symbol_id}
            ).fetchone()

            if not result:
                return None

            return {
                "id": result[0],
                "ticker": result[1],
                "name": result[2],
                "name_en": result[3],
                "category": result[4],
                "sub_category": result[5],
                "is_active": result[6],
                "is_calculated": result[7],
                "base_symbol_id": result[8],
                "fx_symbol_id": result[9],
                "operation": result[10],
            }
        finally:
            self._close_session(session)

    def get_all_symbols(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """全銘柄を取得"""
        session = self._get_session()
        try:
            query = """
                SELECT id, ticker, name, name_en, category, sub_category,
                       is_active, is_calculated, base_symbol_id, fx_symbol_id, operation
                FROM public.market_symbols
            """
            if active_only:
                query += " WHERE is_active = TRUE"
            query += " ORDER BY category, sub_category, id"

            results = session.execute(text(query)).fetchall()

            return [
                {
                    "id": r[0],
                    "ticker": r[1],
                    "name": r[2],
                    "name_en": r[3],
                    "category": r[4],
                    "sub_category": r[5],
                    "is_active": r[6],
                    "is_calculated": r[7],
                    "base_symbol_id": r[8],
                    "fx_symbol_id": r[9],
                    "operation": r[10],
                }
                for r in results
            ]
        finally:
            self._close_session(session)

    def get_non_calculated_symbols(self) -> List[Dict[str, Any]]:
        """計算値でない銘柄のみ取得（yfinance取得対象）"""
        session = self._get_session()
        try:
            results = session.execute(
                text("""
                    SELECT id, ticker, name, name_en, category, sub_category
                    FROM public.market_symbols
                    WHERE is_active = TRUE AND is_calculated = FALSE
                    ORDER BY category, sub_category, id
                """)
            ).fetchall()

            return [
                {
                    "id": r[0],
                    "ticker": r[1],
                    "name": r[2],
                    "name_en": r[3],
                    "category": r[4],
                    "sub_category": r[5],
                }
                for r in results
            ]
        finally:
            self._close_session(session)

    # =========================================================================
    # 日足データ
    # =========================================================================

    def get_daily_data(
        self,
        symbol_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """日足データを取得"""
        session = self._get_session()
        try:
            query = """
                SELECT date, open, high, low, close, volume
                FROM timeseries.market_daily_data
                WHERE symbol_id = :symbol_id
            """
            params: Dict[str, Any] = {"symbol_id": symbol_id}

            if start_date:
                query += " AND date >= :start_date"
                params["start_date"] = start_date

            if end_date:
                query += " AND date <= :end_date"
                params["end_date"] = end_date

            query += " ORDER BY date ASC"

            if limit:
                query += " LIMIT :limit"
                params["limit"] = limit

            results = session.execute(text(query), params).fetchall()

            return [
                {
                    "date": r[0].isoformat() if isinstance(r[0], date) else str(r[0]),
                    "open": float(r[1]) if r[1] else None,
                    "high": float(r[2]) if r[2] else None,
                    "low": float(r[3]) if r[3] else None,
                    "close": float(r[4]) if r[4] else None,
                    "volume": int(r[5]) if r[5] else 0,
                }
                for r in results
            ]
        finally:
            self._close_session(session)

    def get_latest_daily_date(self, symbol_id: str) -> Optional[date]:
        """最新の日足データの日付を取得"""
        session = self._get_session()
        try:
            result = session.execute(
                text("""
                    SELECT MAX(date)
                    FROM timeseries.market_daily_data
                    WHERE symbol_id = :symbol_id
                """),
                {"symbol_id": symbol_id}
            ).scalar()

            return result
        finally:
            self._close_session(session)

    def get_daily_data_count(self, symbol_id: str) -> int:
        """日足データの件数を取得"""
        session = self._get_session()
        try:
            result = session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM timeseries.market_daily_data
                    WHERE symbol_id = :symbol_id
                """),
                {"symbol_id": symbol_id}
            ).scalar()

            return result or 0
        finally:
            self._close_session(session)

    def upsert_daily_data(
        self,
        symbol_id: str,
        data: List[Dict[str, Any]],
        source: str = "yfinance"
    ) -> int:
        """日足データをUPSERT（存在すれば更新、なければ挿入）"""
        if not data:
            return 0

        session = self._get_session()
        try:
            # バッチでUPSERT
            count = 0
            for record in data:
                session.execute(
                    text("""
                        INSERT INTO timeseries.market_daily_data
                            (symbol_id, date, open, high, low, close, volume, source)
                        VALUES
                            (:symbol_id, :date, :open, :high, :low, :close, :volume, :source)
                        ON CONFLICT (symbol_id, date)
                        DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            source = EXCLUDED.source
                    """),
                    {
                        "symbol_id": symbol_id,
                        "date": record["date"],
                        "open": record.get("open"),
                        "high": record.get("high"),
                        "low": record.get("low"),
                        "close": record.get("close"),
                        "volume": record.get("volume", 0),
                        "source": source,
                    }
                )
                count += 1

            session.commit()
            return count
        except Exception as e:
            session.rollback()
            raise e
        finally:
            self._close_session(session)

    def delete_old_daily_data(self, symbol_id: str, before_date: date) -> int:
        """古い日足データを削除"""
        session = self._get_session()
        try:
            result = session.execute(
                text("""
                    DELETE FROM timeseries.market_daily_data
                    WHERE symbol_id = :symbol_id AND date < :before_date
                """),
                {"symbol_id": symbol_id, "before_date": before_date}
            )
            session.commit()
            return result.rowcount
        except Exception as e:
            session.rollback()
            raise e
        finally:
            self._close_session(session)

    # =========================================================================
    # 分足データ
    # =========================================================================

    def upsert_intraday_data(
        self,
        symbol_id: str,
        data: List[Dict[str, Any]],
        interval: str,
        source: str = "yfinance"
    ) -> int:
        """分足データをUPSERT"""
        if not data:
            return 0

        session = self._get_session()
        try:
            count = 0
            for record in data:
                session.execute(
                    text("""
                        INSERT INTO timeseries.market_intraday_data
                            (symbol_id, timestamp, interval, open, high, low, close, volume, source)
                        VALUES
                            (:symbol_id, :timestamp, :interval, :open, :high, :low, :close, :volume, :source)
                        ON CONFLICT (symbol_id, timestamp, interval)
                        DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            source = EXCLUDED.source
                    """),
                    {
                        "symbol_id": symbol_id,
                        "timestamp": record["timestamp"],
                        "interval": interval,
                        "open": record.get("open"),
                        "high": record.get("high"),
                        "low": record.get("low"),
                        "close": record.get("close"),
                        "volume": record.get("volume", 0),
                        "source": source,
                    }
                )
                count += 1

            session.commit()
            return count
        except Exception as e:
            session.rollback()
            raise e
        finally:
            self._close_session(session)

    def get_intraday_data(
        self,
        symbol_id: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """分足データを取得"""
        session = self._get_session()
        try:
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM timeseries.market_intraday_data
                WHERE symbol_id = :symbol_id AND interval = :interval
            """
            params: Dict[str, Any] = {"symbol_id": symbol_id, "interval": interval}

            if start_time:
                query += " AND timestamp >= :start_time"
                params["start_time"] = start_time

            if end_time:
                query += " AND timestamp <= :end_time"
                params["end_time"] = end_time

            query += " ORDER BY timestamp ASC"

            if limit:
                query += " LIMIT :limit"
                params["limit"] = limit

            results = session.execute(text(query), params).fetchall()

            return [
                {
                    "timestamp": r[0].isoformat() if isinstance(r[0], datetime) else str(r[0]),
                    "open": float(r[1]) if r[1] else None,
                    "high": float(r[2]) if r[2] else None,
                    "low": float(r[3]) if r[3] else None,
                    "close": float(r[4]) if r[4] else None,
                    "volume": int(r[5]) if r[5] else 0,
                }
                for r in results
            ]
        finally:
            self._close_session(session)

    def get_intraday_data_batch(
        self,
        symbol_id: str,
        interval: str,
        time_ranges: List[tuple[datetime, datetime]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        複数の時間範囲に対して分足データをバッチ取得

        Args:
            symbol_id: 銘柄ID
            interval: 足種
            time_ranges: [(start_time, end_time), ...] のリスト

        Returns:
            {
                "2024-12-02T15:00:00+00:00": [...],  # 時間範囲の開始時刻をキーにしたデータ
                "2024-11-04T15:00:00+00:00": [...],
            }
        """
        if not time_ranges:
            return {}

        session = self._get_session()
        try:
            # 全時間範囲をカバーする最小・最大時刻を取得
            all_starts = [tr[0] for tr in time_ranges]
            all_ends = [tr[1] for tr in time_ranges]
            min_time = min(all_starts)
            max_time = max(all_ends)

            # 1回のクエリで必要な範囲のデータを全て取得
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM timeseries.market_intraday_data
                WHERE symbol_id = :symbol_id
                  AND interval = :interval
                  AND timestamp >= :min_time
                  AND timestamp <= :max_time
                ORDER BY timestamp ASC
            """
            results = session.execute(
                text(query),
                {
                    "symbol_id": symbol_id,
                    "interval": interval,
                    "min_time": min_time,
                    "max_time": max_time,
                }
            ).fetchall()

            # 全データをリストに変換
            all_data = [
                {
                    "timestamp": r[0],
                    "timestamp_str": r[0].isoformat() if isinstance(r[0], datetime) else str(r[0]),
                    "open": float(r[1]) if r[1] else None,
                    "high": float(r[2]) if r[2] else None,
                    "low": float(r[3]) if r[3] else None,
                    "close": float(r[4]) if r[4] else None,
                    "volume": int(r[5]) if r[5] else 0,
                }
                for r in results
            ]

            # 各時間範囲に対してデータを振り分け
            result_dict: Dict[str, List[Dict[str, Any]]] = {}
            for start_time, end_time in time_ranges:
                key = start_time.isoformat()
                result_dict[key] = []

                for record in all_data:
                    ts = record["timestamp"]
                    if start_time <= ts <= end_time:
                        result_dict[key].append({
                            "timestamp": record["timestamp_str"],
                            "open": record["open"],
                            "high": record["high"],
                            "low": record["low"],
                            "close": record["close"],
                            "volume": record["volume"],
                        })

            return result_dict
        finally:
            self._close_session(session)

    # =========================================================================
    # 分足同期状態管理
    # =========================================================================

    def get_sync_status(
        self,
        symbol_id: str,
        interval: str
    ) -> Optional[Dict[str, Any]]:
        """銘柄×足種の同期状態を取得"""
        session = self._get_session()
        try:
            result = session.execute(
                text("""
                    SELECT symbol_id, interval, last_sync_at, data_start_date, data_end_date,
                           record_count, sync_status, error_message, created_at, updated_at
                    FROM public.market_intraday_sync_status
                    WHERE symbol_id = :symbol_id AND interval = :interval
                """),
                {"symbol_id": symbol_id, "interval": interval}
            ).fetchone()

            if not result:
                return None

            return {
                "symbol_id": result[0],
                "interval": result[1],
                "last_sync_at": result[2].isoformat() if result[2] else None,
                "data_start_date": result[3].isoformat() if result[3] else None,
                "data_end_date": result[4].isoformat() if result[4] else None,
                "record_count": result[5],
                "sync_status": result[6],
                "error_message": result[7],
                "created_at": result[8].isoformat() if result[8] else None,
                "updated_at": result[9].isoformat() if result[9] else None,
            }
        finally:
            self._close_session(session)

    def get_all_sync_status(self) -> List[Dict[str, Any]]:
        """全銘柄の同期状態を取得"""
        session = self._get_session()
        try:
            results = session.execute(
                text("""
                    SELECT symbol_id, interval, last_sync_at, data_start_date, data_end_date,
                           record_count, sync_status, error_message
                    FROM public.market_intraday_sync_status
                    ORDER BY symbol_id, interval
                """)
            ).fetchall()

            return [
                {
                    "symbol_id": r[0],
                    "interval": r[1],
                    "last_sync_at": r[2].isoformat() if r[2] else None,
                    "data_start_date": r[3].isoformat() if r[3] else None,
                    "data_end_date": r[4].isoformat() if r[4] else None,
                    "record_count": r[5],
                    "sync_status": r[6],
                    "error_message": r[7],
                }
                for r in results
            ]
        finally:
            self._close_session(session)

    def upsert_sync_status(
        self,
        symbol_id: str,
        interval: str,
        last_sync_at: Optional[datetime] = None,
        data_start_date: Optional[date] = None,
        data_end_date: Optional[date] = None,
        record_count: int = 0,
        sync_status: str = "pending",
        error_message: Optional[str] = None
    ) -> None:
        """同期状態をUPSERT"""
        session = self._get_session()
        try:
            session.execute(
                text("""
                    INSERT INTO public.market_intraday_sync_status
                        (symbol_id, interval, last_sync_at, data_start_date, data_end_date,
                         record_count, sync_status, error_message)
                    VALUES
                        (:symbol_id, :interval, :last_sync_at, :data_start_date, :data_end_date,
                         :record_count, :sync_status, :error_message)
                    ON CONFLICT (symbol_id, interval)
                    DO UPDATE SET
                        last_sync_at = EXCLUDED.last_sync_at,
                        data_start_date = EXCLUDED.data_start_date,
                        data_end_date = EXCLUDED.data_end_date,
                        record_count = EXCLUDED.record_count,
                        sync_status = EXCLUDED.sync_status,
                        error_message = EXCLUDED.error_message
                """),
                {
                    "symbol_id": symbol_id,
                    "interval": interval,
                    "last_sync_at": last_sync_at,
                    "data_start_date": data_start_date,
                    "data_end_date": data_end_date,
                    "record_count": record_count,
                    "sync_status": sync_status,
                    "error_message": error_message,
                }
            )
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            self._close_session(session)

    def update_sync_status_syncing(self, symbol_id: str, interval: str) -> None:
        """同期開始状態に更新"""
        session = self._get_session()
        try:
            session.execute(
                text("""
                    UPDATE public.market_intraday_sync_status
                    SET sync_status = 'syncing', error_message = NULL
                    WHERE symbol_id = :symbol_id AND interval = :interval
                """),
                {"symbol_id": symbol_id, "interval": interval}
            )
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            self._close_session(session)

    def delete_old_intraday_data(
        self,
        symbol_id: str,
        interval: str,
        before_date: datetime
    ) -> int:
        """古い分足データを削除"""
        session = self._get_session()
        try:
            result = session.execute(
                text("""
                    DELETE FROM timeseries.market_intraday_data
                    WHERE symbol_id = :symbol_id
                      AND interval = :interval
                      AND timestamp < :before_date
                """),
                {
                    "symbol_id": symbol_id,
                    "interval": interval,
                    "before_date": before_date,
                }
            )
            session.commit()
            return result.rowcount
        except Exception as e:
            session.rollback()
            raise e
        finally:
            self._close_session(session)

    def get_intraday_data_range(
        self,
        symbol_id: str,
        interval: str
    ) -> Optional[Dict[str, Any]]:
        """分足データの日付範囲とレコード数を取得"""
        session = self._get_session()
        try:
            result = session.execute(
                text("""
                    SELECT MIN(timestamp), MAX(timestamp), COUNT(*)
                    FROM timeseries.market_intraday_data
                    WHERE symbol_id = :symbol_id AND interval = :interval
                """),
                {"symbol_id": symbol_id, "interval": interval}
            ).fetchone()

            if not result or result[2] == 0:
                return None

            return {
                "min_timestamp": result[0],
                "max_timestamp": result[1],
                "count": result[2],
            }
        finally:
            self._close_session(session)

    # =========================================================================
    # 更新ログ
    # =========================================================================

    def log_update(
        self,
        data_type: str,
        status: str,
        records_updated: int = 0,
        symbol_id: Optional[str] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> int:
        """更新ログを記録"""
        session = self._get_session()
        try:
            started = started_at or datetime.utcnow()
            completed = completed_at or datetime.utcnow()
            duration = (completed - started).total_seconds() if completed else None

            result = session.execute(
                text("""
                    INSERT INTO public.market_data_update_logs
                        (symbol_id, data_type, status, records_updated, error_message,
                         started_at, completed_at, duration_seconds)
                    VALUES
                        (:symbol_id, :data_type, :status, :records_updated, :error_message,
                         :started_at, :completed_at, :duration_seconds)
                    RETURNING id
                """),
                {
                    "symbol_id": symbol_id,
                    "data_type": data_type,
                    "status": status,
                    "records_updated": records_updated,
                    "error_message": error_message,
                    "started_at": started,
                    "completed_at": completed,
                    "duration_seconds": duration,
                }
            )
            session.commit()
            return result.scalar()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            self._close_session(session)


# シングルトンインスタンス
market_repository = MarketRepository()
