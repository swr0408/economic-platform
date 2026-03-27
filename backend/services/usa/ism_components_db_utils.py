"""
ISM Components DB蓄積ユーティリティ

ism_components テーブルへのデータ保存・読み込みを共通化。
製造業・非製造業の両方で共有。

テーブル構造:
    type              VARCHAR(16)  -- 'manufacturing' or 'non_manufacturing'
    date              DATE         -- データ日付（YYYY-MM-01）
    new_orders        DECIMAL(5,1)
    production        DECIMAL(5,1)  -- 製造業のみ
    business_activity DECIMAL(5,1)  -- 非製造業のみ
    employment        DECIMAL(5,1)
    supplier_deliveries DECIMAL(5,1)
    prices            DECIMAL(5,1)
    inventories       DECIMAL(5,1)
    source            VARCHAR(16)  -- 'dbnomics', 'csv', 'fmp'
    PRIMARY KEY (type, date)
"""
import logging
from datetime import date
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 値カラム一覧
VALUE_COLUMNS = [
    "new_orders", "production", "business_activity",
    "employment", "supplier_deliveries", "prices", "inventories",
]


def upsert_ism_components(
    type_: str,
    data_list: List[Dict],
    source: str = "dbnomics",
) -> int:
    """ISM Componentsデータを一括UPSERT

    Args:
        type_: 'manufacturing' or 'non_manufacturing'
        data_list: [{"date": "YYYY-MM-01", "new_orders": 57.1, ...}, ...]
        source: データソース ('dbnomics', 'csv', 'fmp')

    Returns:
        追加/更新件数
    """
    if not data_list:
        return 0

    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        count = 0
        with SessionLocal() as session:
            for item in data_list:
                date_str = item.get("date")
                if not date_str:
                    continue

                params = {
                    "type": type_,
                    "dt": date_str,
                    "new_orders": item.get("new_orders"),
                    "production": item.get("production"),
                    "business_activity": item.get("business_activity"),
                    "employment": item.get("employment"),
                    "supplier_deliveries": item.get("supplier_deliveries"),
                    "prices": item.get("prices"),
                    "inventories": item.get("inventories"),
                    "source": source,
                }

                session.execute(text("""
                    INSERT INTO ism_components
                        (type, date, new_orders, production, business_activity,
                         employment, supplier_deliveries, prices, inventories,
                         source, updated_at)
                    VALUES
                        (:type, :dt, :new_orders, :production, :business_activity,
                         :employment, :supplier_deliveries, :prices, :inventories,
                         :source, CURRENT_TIMESTAMP)
                    ON CONFLICT (type, date)
                    DO UPDATE SET
                        new_orders = COALESCE(EXCLUDED.new_orders, ism_components.new_orders),
                        production = COALESCE(EXCLUDED.production, ism_components.production),
                        business_activity = COALESCE(EXCLUDED.business_activity, ism_components.business_activity),
                        employment = COALESCE(EXCLUDED.employment, ism_components.employment),
                        supplier_deliveries = COALESCE(EXCLUDED.supplier_deliveries, ism_components.supplier_deliveries),
                        prices = COALESCE(EXCLUDED.prices, ism_components.prices),
                        inventories = COALESCE(EXCLUDED.inventories, ism_components.inventories),
                        source = EXCLUDED.source,
                        updated_at = CURRENT_TIMESTAMP
                """), params)
                count += 1

            session.commit()

        logger.info(f"[ISM-DB] {type_}: upserted {count} records (source={source})")
        return count

    except Exception as e:
        logger.warning(f"[ISM-DB] {type_}: upsert failed: {e}")
        return 0


def load_ism_components(type_: str) -> List[Dict]:
    """DBからISM Componentsの全データを取得

    Args:
        type_: 'manufacturing' or 'non_manufacturing'

    Returns:
        [{"date": "YYYY-MM-01", "new_orders": 57.1, ...}, ...] 日付昇順
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            rows = session.execute(text("""
                SELECT date, new_orders, production, business_activity,
                       employment, supplier_deliveries, prices, inventories
                FROM ism_components
                WHERE type = :type
                ORDER BY date ASC
            """), {"type": type_}).fetchall()

        result = []
        for row in rows:
            date_val = row[0]
            date_str = date_val.isoformat() if isinstance(date_val, date) else str(date_val)
            item = {
                "date": date_str,
                "new_orders": float(row[1]) if row[1] is not None else None,
                "production": float(row[2]) if row[2] is not None else None,
                "business_activity": float(row[3]) if row[3] is not None else None,
                "employment": float(row[4]) if row[4] is not None else None,
                "supplier_deliveries": float(row[5]) if row[5] is not None else None,
                "prices": float(row[6]) if row[6] is not None else None,
                "inventories": float(row[7]) if row[7] is not None else None,
            }
            result.append(item)

        logger.info(f"[ISM-DB] {type_}: loaded {len(result)} records from DB")
        return result

    except Exception as e:
        logger.warning(f"[ISM-DB] {type_}: load failed: {e}")
        return []


def get_latest_date(type_: str, source: Optional[str] = None) -> Optional[str]:
    """指標のDB内最新日付を取得

    Args:
        type_: 'manufacturing' or 'non_manufacturing'
        source: フィルタするソース（None=全ソース、'dbnomics'=DBnomicsのみ等）
    """
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        if source:
            query = text("""
                SELECT MAX(date) FROM ism_components
                WHERE type = :type AND source = :source
            """)
            params = {"type": type_, "source": source}
        else:
            query = text("""
                SELECT MAX(date) FROM ism_components WHERE type = :type
            """)
            params = {"type": type_}

        with SessionLocal() as session:
            row = session.execute(query, params).scalar()

        if row:
            return row.isoformat() if isinstance(row, date) else str(row)
        return None

    except Exception as e:
        logger.warning(f"[ISM-DB] {type_}: get_latest_date failed: {e}")
        return None


def get_record_count(type_: str) -> int:
    """指標のレコード数を取得"""
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            return session.execute(text("""
                SELECT COUNT(*) FROM ism_components WHERE type = :type
            """), {"type": type_}).scalar() or 0
    except Exception:
        return 0
