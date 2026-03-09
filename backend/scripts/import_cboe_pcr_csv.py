"""
CBOE Put/Call Ratio CSVインポートスクリプト

CSV形式: DATE,CALLS,PUTS,TOTAL,P/C Ratio
日付形式: MM/DD/YYYY
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from core.database import SessionLocal
from sqlalchemy import text
from datetime import datetime


def import_cboe_pcr_csv(csv_path: str):
    """CSVからCBOE PCRデータをインポート"""
    print(f"Reading CSV: {csv_path}")
    df = pd.read_csv(csv_path, encoding="utf-8")
    print(f"Total rows: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Sample:\n{df.head(3)}")

    inserted = 0
    skipped = 0
    errors = 0

    with SessionLocal() as session:
        # テーブル作成
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS cboe_put_call_ratio (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                total_pcr NUMERIC(10, 4),
                source VARCHAR(50) DEFAULT 'CBOE',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                CONSTRAINT cboe_put_call_ratio_date_unique UNIQUE (date)
            )
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_cboe_put_call_ratio_date
            ON cboe_put_call_ratio (date DESC)
        """))
        session.commit()

        for _, row in df.iterrows():
            try:
                # 日付パース (MM/DD/YYYY)
                date_str = str(row["DATE"]).strip()
                try:
                    dt = datetime.strptime(date_str, "%m/%d/%Y")
                except ValueError:
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                    except ValueError:
                        errors += 1
                        continue

                date_val = dt.strftime("%Y-%m-%d")

                # P/C Ratio
                pcr_val = row.get("P/C Ratio")
                if pd.isna(pcr_val):
                    skipped += 1
                    continue

                pcr_float = float(pcr_val)

                session.execute(text("""
                    INSERT INTO cboe_put_call_ratio (date, total_pcr, source)
                    VALUES (:date, :pcr, 'CSV')
                    ON CONFLICT (date) DO UPDATE SET
                        total_pcr = EXCLUDED.total_pcr,
                        updated_at = NOW()
                """), {"date": date_val, "pcr": pcr_float})
                inserted += 1

            except Exception as e:
                print(f"Error at row {_}: {e}")
                errors += 1

        session.commit()

    print(f"\nResults: inserted={inserted}, skipped={skipped}, errors={errors}")
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "csv_import", "cboe_pcr_full.csv"
    )
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]

    import_cboe_pcr_csv(csv_path)
