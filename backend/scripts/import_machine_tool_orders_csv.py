#!/usr/bin/env python
"""
Machine Tool Orders CSV Import Script

Import YoY data from CSV file to database.
Only imports data before Excel data starts (before 2021).

Usage:
    python scripts/import_machine_tool_orders_csv.py [--all]
"""
import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Add backend module path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CSV file path
CSV_FILE = Path(__file__).parent.parent / "data" / "csv_import" / "工作機械受注.csv"

# Excel data starts from 2021, so we import CSV data before that
EXCEL_START_YEAR = 2021


def parse_csv(csv_path: Path) -> list[dict]:
    """
    Parse CSV file and extract data.

    Args:
        csv_path: Path to CSV file

    Returns:
        List of data dictionaries
    """
    data_list = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            date_str = row.get('公表日', '').strip()
            value_str = row.get('結果', '').strip()

            if not date_str or not value_str:
                continue

            try:
                # Parse date (format: YYYY/M)
                parts = date_str.split('/')
                year = int(parts[0])
                month = int(parts[1])

                # Parse value (YoY percentage)
                value = float(value_str)

                data_list.append({
                    'date': f"{year}-{month:02d}-01",
                    'year': year,
                    'month': month,
                    'total_yoy': value,
                    'data_type': 'kakuhou',
                    'source': 'CSV'
                })

            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse row: {row}, error: {e}")
                continue

    return data_list


def clear_existing_data():
    """Clear existing data from DB before import."""
    try:
        with SessionLocal() as session:
            query = text("DELETE FROM japan_machine_tool_orders_history")
            result = session.execute(query)
            session.commit()
            logger.info(f"Cleared {result.rowcount} existing records")
            return True
    except Exception as e:
        logger.error(f"Failed to clear existing data: {e}")
        return False


def save_to_db(data: dict) -> bool:
    """
    Save data to DB (UPSERT).

    Args:
        data: Data dictionary to save

    Returns:
        True if successful
    """
    try:
        with SessionLocal() as session:
            query = text("""
                INSERT INTO japan_machine_tool_orders_history
                (date, total_yoy, data_type, source, updated_at)
                VALUES (:date, :total_yoy, :data_type, :source, NOW())
                ON CONFLICT (date) DO UPDATE SET
                    total_yoy = EXCLUDED.total_yoy,
                    data_type = EXCLUDED.data_type,
                    source = EXCLUDED.source,
                    updated_at = NOW()
            """)
            session.execute(query, data)
            session.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to save data to DB: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Import Machine Tool Orders YoY data from CSV')
    parser.add_argument('--all', action='store_true', help='Import all data (not just before Excel)')
    parser.add_argument('--dry-run', action='store_true', help='Do not save to DB')
    parser.add_argument('--clear', action='store_true', help='Clear existing data before import')
    args = parser.parse_args()

    if not CSV_FILE.exists():
        logger.error(f"CSV file not found: {CSV_FILE}")
        return

    logger.info(f"Reading CSV file: {CSV_FILE}")
    data_list = parse_csv(CSV_FILE)
    logger.info(f"Parsed {len(data_list)} records from CSV")

    # Filter to only import data before Excel start year (unless --all)
    if not args.all:
        data_list = [d for d in data_list if d['year'] < EXCEL_START_YEAR]
        logger.info(f"Filtered to {len(data_list)} records (before {EXCEL_START_YEAR})")

    if args.clear and not args.dry_run:
        clear_existing_data()

    success_count = 0
    fail_count = 0

    for data in data_list:
        if args.dry_run:
            logger.info(f"[DRY RUN] Would save: {data['date']} -> {data['total_yoy']}%")
            success_count += 1
        else:
            if save_to_db(data):
                logger.info(f"Saved: {data['date']} -> {data['total_yoy']}%")
                success_count += 1
            else:
                fail_count += 1

    logger.info(f"Import completed: {success_count} success, {fail_count} failed")


if __name__ == '__main__':
    main()
