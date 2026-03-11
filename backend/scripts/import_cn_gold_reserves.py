"""
中国人民銀行 金準備 CSV → DB インポートスクリプト

CSV: backend/data/cache/china/policy/cn_gold_reserves_cache.csv
DB:  cn_gold_reserves テーブル

Usage:
    python backend/scripts/import_cn_gold_reserves.py
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
    / "china"
    / "policy"
    / "cn_gold_reserves_cache.csv"
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cn_gold_reserves (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    gold_ounces_wan DOUBLE PRECISION,
    gold_value_usd_yi DOUBLE PRECISION,
    source VARCHAR(50) DEFAULT 'PBOC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cn_gold_reserves_date ON cn_gold_reserves(date);
"""


def import_csv():
    if not CSV_FILE.exists():
        print(f"CSV not found: {CSV_FILE}")
        print("Run scrape_pboc_gold_reserves.py first.")
        return

    records = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ounces = row.get("gold_ounces_wan", "")
            usd = row.get("gold_value_usd_yi", "")
            records.append({
                "date": row["date"],
                "gold_ounces_wan": float(ounces) if ounces else None,
                "gold_value_usd_yi": float(usd) if usd else None,
            })

    if not records:
        print("No records in CSV")
        return

    print(f"CSV: {len(records)} records ({records[0]['date']} ~ {records[-1]['date']})")

    with SessionLocal() as session:
        for stmt in CREATE_TABLE_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                session.execute(text(stmt))
        session.commit()
    print("Table ensured")

    with SessionLocal() as session:
        for rec in records:
            session.execute(
                text("""
                    INSERT INTO cn_gold_reserves
                        (date, gold_ounces_wan, gold_value_usd_yi, source)
                    VALUES
                        (:date, :gold_ounces_wan, :gold_value_usd_yi, 'PBOC_CSV')
                    ON CONFLICT (date) DO UPDATE SET
                        gold_ounces_wan = EXCLUDED.gold_ounces_wan,
                        gold_value_usd_yi = EXCLUDED.gold_value_usd_yi,
                        updated_at = NOW()
                """),
                rec,
            )
        session.commit()

    print(f"Imported {len(records)} records")

    with SessionLocal() as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM cn_gold_reserves")
        ).fetchone()
        print(f"DB count: {result[0]}")
        result = session.execute(
            text("SELECT MIN(date), MAX(date) FROM cn_gold_reserves")
        ).fetchone()
        print(f"DB range: {result[0]} ~ {result[1]}")


if __name__ == "__main__":
    import_csv()
