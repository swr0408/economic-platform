"""
NBS月次データ DB蓄積ユーティリティ

nbs_monthly_data テーブルへのCSVインポートとAPIデータ蓄積を共通化。
複数指標（PPI、失業率、商業住宅販売等）で共有。

テーブル構造:
    indicator VARCHAR(64)  -- 指標ID（例: cn_ppi_yoy, cn_unemployment_total）
    date      DATE         -- データ日付（YYYY-MM-01）
    value     DECIMAL      -- 値
    source    VARCHAR(16)  -- 'csv' or 'api'
    PRIMARY KEY (indicator, date)
"""
import logging
from datetime import date
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def upsert_nbs_data(
    indicator: str,
    data: Dict[str, float],
    source: str = "api",
) -> int:
    """NBS月次データをDBに一括UPSERT

    Args:
        indicator: 指標ID（例: 'cn_ppi_yoy'）
        data: {date_str: value, ...} e.g. {"2026-01-01": -1.4}
        source: データソース ('csv' or 'api')

    Returns:
        追加/更新件数
    """
    if not data:
        return 0

    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        count = 0
        with SessionLocal() as session:
            for date_str, value in data.items():
                session.execute(text("""
                    INSERT INTO nbs_monthly_data (indicator, date, value, source, updated_at)
                    VALUES (:ind, :dt, :val, :src, CURRENT_TIMESTAMP)
                    ON CONFLICT (indicator, date)
                    DO UPDATE SET value = :val, source = :src, updated_at = CURRENT_TIMESTAMP
                """), {"ind": indicator, "dt": date_str, "val": value, "src": source})
                count += 1
            session.commit()
        logger.info(f"[NBS-DB] {indicator}: upserted {count} records (source={source})")
        return count
    except Exception as e:
        logger.warning(f"[NBS-DB] {indicator}: upsert failed: {e}")
        return 0


def load_nbs_data(indicator: str) -> Dict[str, float]:
    """DBから指標の全データを取得

    Args:
        indicator: 指標ID

    Returns:
        {date_str: value, ...} 日付昇順
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            rows = session.execute(text("""
                SELECT date, value
                FROM nbs_monthly_data
                WHERE indicator = :ind
                ORDER BY date ASC
            """), {"ind": indicator}).fetchall()

        result = {}
        for row in rows:
            date_str = row[0].isoformat() if isinstance(row[0], date) else str(row[0])
            result[date_str] = float(row[1])
        return result
    except Exception as e:
        logger.warning(f"[NBS-DB] {indicator}: load failed: {e}")
        return {}


def load_nbs_multi(indicators: List[str]) -> Dict[str, Dict[str, float]]:
    """DBから複数指標のデータを一括取得

    Args:
        indicators: 指標IDリスト

    Returns:
        {indicator: {date_str: value, ...}, ...}
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            # IN句で一括取得
            placeholders = ", ".join(f":ind{i}" for i in range(len(indicators)))
            params = {f"ind{i}": ind for i, ind in enumerate(indicators)}
            rows = session.execute(text(f"""
                SELECT indicator, date, value
                FROM nbs_monthly_data
                WHERE indicator IN ({placeholders})
                ORDER BY indicator, date ASC
            """), params).fetchall()

        result: Dict[str, Dict[str, float]] = {ind: {} for ind in indicators}
        for row in rows:
            ind = row[0]
            date_str = row[1].isoformat() if isinstance(row[1], date) else str(row[1])
            result[ind][date_str] = float(row[2])
        return result
    except Exception as e:
        logger.warning(f"[NBS-DB] multi load failed: {e}")
        return {ind: {} for ind in indicators}


def get_latest_date(indicator: str) -> Optional[str]:
    """指標のDB内最新日付を取得"""
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            row = session.execute(text("""
                SELECT MAX(date) FROM nbs_monthly_data WHERE indicator = :ind
            """), {"ind": indicator}).scalar()

        if row:
            return row.isoformat() if isinstance(row, date) else str(row)
        return None
    except Exception as e:
        logger.warning(f"[NBS-DB] {indicator}: get_latest_date failed: {e}")
        return None


def get_record_count(indicator: str) -> int:
    """指標のレコード数を取得"""
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            return session.execute(text("""
                SELECT COUNT(*) FROM nbs_monthly_data WHERE indicator = :ind
            """), {"ind": indicator}).scalar() or 0
    except Exception as e:
        return 0
