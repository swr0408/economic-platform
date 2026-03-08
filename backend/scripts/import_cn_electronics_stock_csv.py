"""
中国電子機器在庫 CSVインポートスクリプト

CSVは転置ワイド形式（行=指標、列=月）:
  Row 0: Database:Monthly
  Row 1: Month:2012-2017
  Row 2: Indicators,Dec 2017,...
  Row 3+: データ行

対象行:
  "Inventories of Manufacture of Electrical Machinery and Equipment Accumulated Growth Rate(%)"
  → DB indicator: cn_electronics_stock_yoy

3ファイル処理:
  - 中国電子機器在庫2012~2017.csv
  - 中国電子機器在庫2018~2023.csv
  - 中国電子機器在庫2024~.csv
"""
import sys
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
env_path = project_root.parent / ".env"
load_dotenv(env_path)

TARGET_INDICATOR = "Inventories of Manufacture of Electrical Machinery and Equipment Accumulated Growth Rate(%)"
DB_INDICATOR = "cn_electronics_stock_yoy"

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


def parse_date_header(header: str) -> str:
    header = header.strip()
    m = re.match(r"([A-Za-z]+)\.?\s*(\d{4})", header)
    if m:
        month_str = m.group(1).lower()
        year = int(m.group(2))
        month = MONTH_MAP.get(month_str)
        if month:
            return f"{year}-{month:02d}-01"
    raise ValueError(f"Cannot parse date header: '{header}'")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import China Electronics Stock CSV to nbs_monthly_data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    csv_dir = Path(__file__).parent.parent / "data" / "csv_import"
    files = [
        "中国電子機器在庫2012~2017.csv",
        "中国電子機器在庫2018~2023.csv",
        "中国電子機器在庫2024~.csv",
    ]

    all_data = {}

    for filename in files:
        file_path = csv_dir / filename
        if not file_path.exists():
            print(f"[SKIP] Not found: {file_path}")
            continue

        print(f"\nProcessing: {filename}")

        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Row 2: header
        headers = lines[2].strip().split(",")
        dates = []
        for h in headers[1:]:
            h = h.strip()
            if not h:
                dates.append(None)
                continue
            try:
                dates.append(parse_date_header(h))
            except ValueError:
                dates.append(None)

        # Find target row
        for line in lines[3:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if parts[0].strip() == TARGET_INDICATOR:
                for i, val_str in enumerate(parts[1:]):
                    if i >= len(dates) or dates[i] is None:
                        continue
                    val_str = val_str.strip()
                    if not val_str:
                        continue
                    try:
                        all_data[dates[i]] = float(val_str)
                    except (ValueError, TypeError):
                        continue
                print(f"  Found {len([v for v in parts[1:] if v.strip()])} values")
                break

    print(f"\nTotal unique records: {len(all_data)}")
    if all_data:
        print(f"Range: {min(all_data.keys())} ~ {max(all_data.keys())}")
        print(f"Sample latest: {sorted(all_data.keys())[-1]} = {all_data[sorted(all_data.keys())[-1]]}")

    if args.dry_run:
        print("(DRY RUN)")
        return

    from services.china.nbs_db_utils import upsert_nbs_data
    count = upsert_nbs_data(DB_INDICATOR, all_data, source="csv")
    print(f"DB upserted: {count}")


if __name__ == "__main__":
    main()
