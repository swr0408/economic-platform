"""
SGE Au(T+D) Excel import script

Import historical daily data from 每日行情数据{yyyymm}.xlsx files (27 files).
Excel columns:
  0: 序号, 1: 日期, 2: 合约, 3: 开盘价, 4: 最高价, 5: 最低价, 6: 收盘价,
  7: 涨跌（元）, 8: 涨跌幅, 9: 加权平均価, 10: 成交量（kg）,
  11: 成交金额（元）, 12: 市場持仓（手）, 13: 交収方向, 14: 交収量（手）
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from core.database import SessionLocal
from sqlalchemy import text

EXCEL_DIR = Path(__file__).parent.parent / "data" / "excel"


def import_all():
    files = sorted(EXCEL_DIR.glob("每日行情数据*.xlsx"))
    if not files:
        print("No Excel files found")
        return

    print(f"Found {len(files)} Excel files")

    all_records = []

    for f in files:
        try:
            df = pd.read_excel(f, header=0)
        except Exception as e:
            print(f"  Error reading {f.name}: {e}")
            continue

        count = 0
        for _, row in df.iterrows():
            try:
                date_val = row.iloc[1]
                if pd.isna(date_val):
                    continue

                # Parse date
                if isinstance(date_val, str):
                    date_str = date_val.strip()
                else:
                    date_str = pd.Timestamp(date_val).strftime("%Y-%m-%d")

                def safe_float(val):
                    if pd.isna(val):
                        return None
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return None

                def safe_int(val):
                    if pd.isna(val):
                        return None
                    try:
                        return int(float(val))
                    except (ValueError, TypeError):
                        return None

                record = {
                    "date": date_str,
                    "open_price": safe_float(row.iloc[3]),
                    "high_price": safe_float(row.iloc[4]),
                    "low_price": safe_float(row.iloc[5]),
                    "close_price": safe_float(row.iloc[6]),
                    "settlement_price": safe_float(row.iloc[9]),
                    "volume_kg": safe_float(row.iloc[10]),
                    "amount_cny": safe_float(row.iloc[11]),
                    "open_interest": safe_int(row.iloc[12]),
                }
                all_records.append(record)
                count += 1
            except Exception as e:
                continue

        print(f"  {f.name}: {count} records")

    if not all_records:
        print("No records to import")
        return

    print(f"\nTotal: {len(all_records)} records")

    # Sort by date
    all_records.sort(key=lambda r: r["date"])
    print(f"Date range: {all_records[0]['date']} ~ {all_records[-1]['date']}")

    # Insert into DB
    with SessionLocal() as session:
        for rec in all_records:
            session.execute(
                text("""
                    INSERT INTO sge_au_td
                        (date, open_price, high_price, low_price, close_price,
                         settlement_price, volume_kg, amount_cny, open_interest, source)
                    VALUES
                        (:date, :open_price, :high_price, :low_price, :close_price,
                         :settlement_price, :volume_kg, :amount_cny, :open_interest, 'SGE_EXCEL')
                    ON CONFLICT (date) DO UPDATE SET
                        open_price = COALESCE(EXCLUDED.open_price, sge_au_td.open_price),
                        high_price = COALESCE(EXCLUDED.high_price, sge_au_td.high_price),
                        low_price = COALESCE(EXCLUDED.low_price, sge_au_td.low_price),
                        close_price = COALESCE(EXCLUDED.close_price, sge_au_td.close_price),
                        settlement_price = COALESCE(EXCLUDED.settlement_price, sge_au_td.settlement_price),
                        volume_kg = COALESCE(EXCLUDED.volume_kg, sge_au_td.volume_kg),
                        amount_cny = COALESCE(EXCLUDED.amount_cny, sge_au_td.amount_cny),
                        open_interest = COALESCE(EXCLUDED.open_interest, sge_au_td.open_interest),
                        updated_at = NOW()
                """),
                rec,
            )
        session.commit()

    print(f"Imported {len(all_records)} records successfully")

    # Verify
    with SessionLocal() as session:
        result = session.execute(text("SELECT COUNT(*) FROM sge_au_td")).fetchone()
        print(f"DB count: {result[0]}")
        result = session.execute(
            text("SELECT MIN(date), MAX(date) FROM sge_au_td")
        ).fetchone()
        print(f"DB range: {result[0]} ~ {result[1]}")


if __name__ == "__main__":
    import_all()
