"""
中国輸出物価指数 CSVファイルからnbs_monthly_dataテーブルへ過去データをインポート

CSV形式: 公表日,結果
  - 公表日: YYYY/M（例: 2010/1）
  - 結果: 指数値（前年同月=100）

取り込む系列:
  - cn_export_prices_index: 輸出物価指数（原数値）
  - cn_export_prices_yoy:   輸出物価 前年比 (%) = index - 100

Usage:
    python backend/scripts/import_cn_export_prices_csv.py
    python backend/scripts/import_cn_export_prices_csv.py --dry-run
"""
import csv
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
env_path = project_root.parent / ".env"
load_dotenv(env_path)


DB_INDICATORS = {
    "index": "cn_export_prices_index",
    "yoy": "cn_export_prices_yoy",
}


def parse_csv(file_path: Path):
    """CSVを解析し、{indicator: {date_str: value}} を返す"""
    index_data = {}
    yoy_data = {}

    with open(file_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)  # 公表日,結果
        print(f"  Header: {header}")

        for row in reader:
            if len(row) < 2:
                continue
            date_raw = row[0].strip()
            value_raw = row[1].strip()

            if not date_raw or not value_raw:
                continue

            # 日付変換: "2010/1" → "2010-01-01"
            parts = date_raw.split("/")
            if len(parts) != 2:
                continue
            year = int(parts[0])
            month = int(parts[1])
            date_str = f"{year}-{month:02d}-01"

            try:
                index_val = float(value_raw)
            except ValueError:
                continue

            index_data[date_str] = round(index_val, 2)
            yoy_data[date_str] = round(index_val - 100, 2)

    return {
        DB_INDICATORS["index"]: index_data,
        DB_INDICATORS["yoy"]: yoy_data,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Import China Export Prices CSV data to nbs_monthly_data table"
    )
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert data")
    args = parser.parse_args()

    csv_dir = Path(__file__).parent.parent / "data" / "csv_import"
    file_path = csv_dir / "中国輸出物価.csv"

    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return

    print(f"\n{'='*60}")
    print(f"Processing: 中国輸出物価.csv")
    print(f"{'='*60}")

    data = parse_csv(file_path)

    total_upserted = 0
    for db_indicator, values in data.items():
        if not values:
            print(f"  {db_indicator}: 0 records (no data)")
            continue

        sorted_dates = sorted(values.keys())
        print(f"  {db_indicator}: {len(values)} records "
              f"({sorted_dates[0]} ~ {sorted_dates[-1]})")

        if args.dry_run:
            sample_latest = sorted_dates[-1]
            print(f"    Sample latest: {sample_latest} = {values[sample_latest]}")
            continue

        from services.china.nbs_db_utils import upsert_nbs_data
        count = upsert_nbs_data(db_indicator, values, source="csv")
        total_upserted += count
        print(f"    → DB upserted: {count}")

    print(f"\n{'='*60}")
    print(f"TOTAL UPSERTED: {total_upserted}")
    if args.dry_run:
        print("(DRY RUN - no data was actually inserted)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
