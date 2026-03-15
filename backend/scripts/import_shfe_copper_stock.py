"""
SHFE Copper Stock 歴史データインポートスクリプト

CSVファイルからDBにインポートする。
CSV列: date, warehouse_stock_tonnes (tonnes)
ソース: commoditieschart.net (2008-10-06~)

Usage:
    cd backend
    python scripts/import_shfe_copper_stock.py
"""
import sys
import logging
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

sys.path.insert(0, ".")
from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent.parent / "data" / "csv_import" / "shfe_cu_warehouse_stocks.csv"


def main():
    if not CSV_PATH.exists():
        logger.error(f"CSV not found: {CSV_PATH}")
        return

    df = pd.read_csv(CSV_PATH)
    logger.info(f"Loaded {len(df)} rows from CSV")
    logger.info(f"Columns: {df.columns.tolist()}")

    inserted = 0

    with SessionLocal() as session:
        # 既存データをクリアして再インポート
        session.execute(text("DELETE FROM shfe_copper_stock"))
        logger.info("Cleared existing data")

        for _, row in df.iterrows():
            date_str = str(row["date"]).strip()
            stock = float(row["warehouse_stock_tonnes"]) if pd.notna(row.get("warehouse_stock_tonnes")) else None

            if stock is None:
                continue

            session.execute(text("""
                INSERT INTO shfe_copper_stock (date, stock_tonnes, source)
                VALUES (:date, :stock, 'commoditieschart')
                ON CONFLICT (date) DO UPDATE SET
                    stock_tonnes = COALESCE(EXCLUDED.stock_tonnes, shfe_copper_stock.stock_tonnes),
                    updated_at = NOW()
            """), {
                "date": date_str,
                "stock": stock,
            })
            inserted += 1

        session.commit()

    logger.info(f"Import complete: {inserted} rows upserted")

    # 確認
    with SessionLocal() as session:
        count = session.execute(text("SELECT COUNT(*) FROM shfe_copper_stock")).scalar()
        first = session.execute(text("SELECT date, stock_tonnes FROM shfe_copper_stock ORDER BY date ASC LIMIT 1")).fetchone()
        last = session.execute(text("SELECT date, stock_tonnes FROM shfe_copper_stock ORDER BY date DESC LIMIT 1")).fetchone()
        logger.info(f"DB total: {count} rows, range: {first[0]} ~ {last[0]}")
        logger.info(f"First: stock={first[1]:,.0f}, Last: stock={last[1]:,.0f}")


if __name__ == "__main__":
    main()
