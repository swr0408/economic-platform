"""
金プレミアム/ディスカウント 初期インポートスクリプト

Excel全履歴(2003~)をDBに格納する。

Usage:
    cd backend
    python scripts/import_gold_premium.py
"""
import sys
import logging
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

sys.path.insert(0, ".")
from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

EXCEL_PATH = Path(__file__).parent.parent / "data" / "excel" / "gold-premiums.xlsx"


def parse_sheet(excel_path: Path, sheet_name: str) -> dict[str, float]:
    """Excelシートから {date_str: value} を返す"""
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
    result: dict[str, float] = {}

    for idx in range(5, len(df)):
        raw_date = df.iloc[idx, 0]
        raw_value = df.iloc[idx, 1]

        if pd.isna(raw_date) or pd.isna(raw_value):
            continue

        if isinstance(raw_date, str):
            date_str = raw_date.strip()
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
        elif hasattr(raw_date, 'strftime'):
            date_str = raw_date.strftime("%Y-%m-%d")
        else:
            continue

        try:
            value = float(raw_value)
        except (ValueError, TypeError):
            continue

        result[date_str] = value

    return result


def import_to_db(china_data: dict[str, float], india_data: dict[str, float]) -> int:
    """DBにUPSERT"""
    all_dates = sorted(set(list(china_data.keys()) + list(india_data.keys())))
    count = 0

    with SessionLocal() as session:
        for date_str in all_dates:
            china_val = china_data.get(date_str)
            india_val = india_data.get(date_str)

            session.execute(
                text("""
                    INSERT INTO gold_premium (date, china, india, source)
                    VALUES (:date, :china, :india, 'excel')
                    ON CONFLICT (date) DO UPDATE SET
                        china = COALESCE(EXCLUDED.china, gold_premium.china),
                        india = COALESCE(EXCLUDED.india, gold_premium.india),
                        updated_at = NOW()
                """),
                {
                    "date": date_str,
                    "china": round(china_val, 6) if china_val is not None else None,
                    "india": round(india_val, 6) if india_val is not None else None,
                },
            )
            count += 1

        session.commit()

    return count


def main():
    if not EXCEL_PATH.exists():
        logger.error(f"Excel not found: {EXCEL_PATH}")
        sys.exit(1)

    logger.info(f"Parsing Excel: {EXCEL_PATH}")

    china_data = parse_sheet(EXCEL_PATH, "Chinese premiums-discounts")
    logger.info(f"China: {len(china_data)} records")

    india_data = parse_sheet(EXCEL_PATH, "Indian premiums-discounts")
    logger.info(f"India: {len(india_data)} records")

    count = import_to_db(china_data, india_data)
    logger.info(f"Imported {count} records to gold_premium")

    # Verify
    with SessionLocal() as session:
        result = session.execute(text("SELECT COUNT(*) FROM gold_premium")).fetchone()
        logger.info(f"Total records in DB: {result[0]}")
        latest = session.execute(
            text("SELECT date, china, india FROM gold_premium ORDER BY date DESC LIMIT 3")
        ).fetchall()
        for r in latest:
            logger.info(f"  {r[0]}: china={r[1]}, india={r[2]}")


if __name__ == "__main__":
    main()
