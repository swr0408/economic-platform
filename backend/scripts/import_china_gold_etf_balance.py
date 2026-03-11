"""
中国金ETF残高 (518880) CSV → DB インポートスクリプト

CSV: backend/data/cache/market/sse_518880_fund_scale_cache.csv
DB:  china_gold_etf_balance テーブル

Usage:
    python backend/scripts/import_china_gold_etf_balance.py
"""

import csv
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import SessionLocal
from sqlalchemy import text

CSV_FILE = (
    Path(__file__).parent.parent
    / "data"
    / "cache"
    / "market"
    / "sse_518880_fund_scale_cache.csv"
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS china_gold_etf_balance (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    fund_code VARCHAR(10) NOT NULL DEFAULT '518880',
    total_shares_wan DOUBLE PRECISION,
    source VARCHAR(50) DEFAULT 'SSE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_china_gold_etf_balance_date ON china_gold_etf_balance(date);
"""


def import_csv():
    if not CSV_FILE.exists():
        print(f"CSV not found: {CSV_FILE}")
        print("Run scrape_sse_fund_scale.py first.")
        return

    # Read CSV
    records = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(
                {
                    "date": row["date"],
                    "fund_code": row["fund_code"],
                    "total_shares_wan": float(row["total_shares_wan"]),
                }
            )

    if not records:
        print("No records in CSV")
        return

    print(f"CSV: {len(records)} records ({records[0]['date']} ~ {records[-1]['date']})")

    # Create table if not exists
    with SessionLocal() as session:
        for stmt in CREATE_TABLE_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                session.execute(text(stmt))
        session.commit()
    print("Table ensured")

    # Upsert
    with SessionLocal() as session:
        for rec in records:
            session.execute(
                text("""
                    INSERT INTO china_gold_etf_balance
                        (date, fund_code, total_shares_wan, source)
                    VALUES
                        (:date, :fund_code, :total_shares_wan, 'SSE_CSV')
                    ON CONFLICT (date) DO UPDATE SET
                        total_shares_wan = EXCLUDED.total_shares_wan,
                        updated_at = NOW()
                """),
                rec,
            )
        session.commit()

    print(f"Imported {len(records)} records")

    # Verify
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM china_gold_etf_balance")
        ).fetchone()
        print(f"DB count: {result[0]}")
        result = session.execute(
            text("SELECT MIN(date), MAX(date) FROM china_gold_etf_balance")
        ).fetchone()
        print(f"DB range: {result[0]} ~ {result[1]}")


if __name__ == "__main__":
    import_csv()
