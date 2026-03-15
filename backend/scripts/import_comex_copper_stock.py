"""
COMEX Copper Stock 歴史データインポートスクリプト

CSVファイルからDBにインポートする。
CSV列: inventory_total, inventory_registered, inventory_eligible (short tons)
注意: registered=0, eligible=0 のレコードはNULLとして扱う（データ欠損）

Usage:
    cd backend
    python scripts/import_comex_copper_stock.py
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

CSV_PATH = Path(__file__).parent.parent / "data" / "csv_import" / "metalcharts_COMEX_HG_20260315.csv"


def main():
    if not CSV_PATH.exists():
        logger.error(f"CSV not found: {CSV_PATH}")
        return

    df = pd.read_csv(CSV_PATH)
    logger.info(f"Loaded {len(df)} rows from CSV")
    logger.info(f"Columns: {df.columns.tolist()}")

    inserted = 0

    with SessionLocal() as session:
        for _, row in df.iterrows():
            date_str = str(row["date"]).strip()
            total = float(row["inventory_total"]) if pd.notna(row.get("inventory_total")) else None
            registered = float(row["inventory_registered"]) if pd.notna(row.get("inventory_registered")) else None
            eligible = float(row["inventory_eligible"]) if pd.notna(row.get("inventory_eligible")) else None

            # registered=0, eligible=0 はデータ欠損として扱う
            if registered == 0 and eligible == 0:
                registered = None
                eligible = None

            session.execute(text("""
                INSERT INTO comex_copper_stock (date, total_tons, registered_tons, eligible_tons, source)
                VALUES (:date, :total, :registered, :eligible, 'metalcharts')
                ON CONFLICT (date) DO UPDATE SET
                    total_tons = COALESCE(EXCLUDED.total_tons, comex_copper_stock.total_tons),
                    registered_tons = COALESCE(EXCLUDED.registered_tons, comex_copper_stock.registered_tons),
                    eligible_tons = COALESCE(EXCLUDED.eligible_tons, comex_copper_stock.eligible_tons),
                    updated_at = NOW()
            """), {
                "date": date_str,
                "total": total,
                "registered": registered,
                "eligible": eligible,
            })
            inserted += 1

        session.commit()

    logger.info(f"Import complete: {inserted} rows upserted")

    # 確認
    with SessionLocal() as session:
        count = session.execute(text("SELECT COUNT(*) FROM comex_copper_stock")).scalar()
        first = session.execute(text("SELECT date, total_tons FROM comex_copper_stock ORDER BY date ASC LIMIT 1")).fetchone()
        last = session.execute(text(
            "SELECT date, total_tons, registered_tons, eligible_tons FROM comex_copper_stock ORDER BY date DESC LIMIT 1"
        )).fetchone()
        logger.info(f"DB total: {count} rows, range: {first[0]} ~ {last[0]}")
        total_str = f"{last[1]:,.0f}" if last[1] else "N/A"
        reg_str = f"{last[2]:,.0f}" if last[2] else "N/A"
        elig_str = f"{last[3]:,.0f}" if last[3] else "N/A"
        logger.info(f"Last: total={total_str}, registered={reg_str}, eligible={elig_str}")


if __name__ == "__main__":
    main()
