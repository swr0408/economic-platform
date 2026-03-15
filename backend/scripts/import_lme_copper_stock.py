"""
LME Copper Stock 歴史データインポートスクリプト

CSVファイルからDBにインポートする。

Usage:
    cd backend
    python scripts/import_lme_copper_stock.py
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

CSV_PATH = Path(__file__).parent.parent / "data" / "csv_import" / "lme_copper_warehouse_stocks_full.csv"


def main():
    if not CSV_PATH.exists():
        logger.error(f"CSV not found: {CSV_PATH}")
        return

    df = pd.read_csv(CSV_PATH)
    logger.info(f"Loaded {len(df)} rows from CSV")

    # 列名確認
    logger.info(f"Columns: {df.columns.tolist()}")

    inserted = 0
    updated = 0

    with SessionLocal() as session:
        for _, row in df.iterrows():
            date_str = str(row["Date"]).strip()
            cash_usd = float(row["LME_Copper_Cash_Settlement_USD"]) if pd.notna(row["LME_Copper_Cash_Settlement_USD"]) else None
            three_month_usd = float(row["LME_Copper_3Month_USD"]) if pd.notna(row["LME_Copper_3Month_USD"]) else None
            stock_tonnes = int(row["LME_Copper_Stock_Tonnes"]) if pd.notna(row["LME_Copper_Stock_Tonnes"]) else None

            result = session.execute(text("""
                INSERT INTO lme_copper_stock (date, cash_usd, three_month_usd, stock_tonnes, source)
                VALUES (:date, :cash_usd, :three_month_usd, :stock_tonnes, 'LME')
                ON CONFLICT (date) DO UPDATE SET
                    cash_usd = EXCLUDED.cash_usd,
                    three_month_usd = EXCLUDED.three_month_usd,
                    stock_tonnes = EXCLUDED.stock_tonnes,
                    updated_at = NOW()
            """), {
                "date": date_str,
                "cash_usd": cash_usd,
                "three_month_usd": three_month_usd,
                "stock_tonnes": stock_tonnes,
            })

            if result.rowcount > 0:
                inserted += 1

        session.commit()

    logger.info(f"Import complete: {inserted} rows upserted")

    # 確認
    with SessionLocal() as session:
        count = session.execute(text("SELECT COUNT(*) FROM lme_copper_stock")).scalar()
        first = session.execute(text("SELECT date, stock_tonnes FROM lme_copper_stock ORDER BY date ASC LIMIT 1")).fetchone()
        last = session.execute(text("SELECT date, stock_tonnes FROM lme_copper_stock ORDER BY date DESC LIMIT 1")).fetchone()
        logger.info(f"DB total: {count} rows, range: {first[0]} ~ {last[0]}")
        logger.info(f"First: stock={first[1]}, Last: stock={last[1]}")


if __name__ == "__main__":
    main()
