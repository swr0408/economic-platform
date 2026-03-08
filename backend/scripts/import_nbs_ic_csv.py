"""
NBS 集積回路生産 CSVファイルからnbs_monthly_dataテーブルへ過去データをインポート

CSVは転置ワイド形式（行=指標、列=月）:
  Row 1: Database:Monthly
  Row 2: Month:2010-
  Row 3: Indicators,Feb. 2026,Jan. 2026,...
  Row 4: Output of Integrated Circuits Current Period(100 million units)
  Row 5: Output of Integrated Circuits Accumulated(100 million units)
  Row 6: Output of Integrated Circuits Growth Rate (The same period last year=100)(%)
  Row 7: Output of Integrated Circuits Accumulated Growth Rate(%)

使用するのは:
  Row 4 → cn_ic_raw (当期生産量 億個)
  Row 6 → cn_ic_yoy (前年比 %) ※ base=100形式なので -100 して%に変換
"""
import sys
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
env_path = project_root.parent / ".env"
load_dotenv(env_path)


INDICATOR_MAP = {
    "Output of Integrated Circuits Current Period(100 million units)": "cn_ic_raw",
    "Output of Integrated Circuits Growth Rate (The same period last year=100)(%)": "cn_ic_yoy",
}


def parse_date_header(header: str) -> str:
    """CSVヘッダーの月表記を YYYY-MM-01 形式に変換"""
    header = header.strip()

    MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4,
        "june": 6, "july": 7, "august": 8, "september": 9,
        "october": 10, "november": 11, "december": 12,
    }

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

    parser = argparse.ArgumentParser(description="Import NBS IC CSV data to nbs_monthly_data table")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert data")
    args = parser.parse_args()

    csv_path = Path(__file__).parent.parent / "data" / "csv_import" / "中国集積回路生産.csv"
    if not csv_path.exists():
        print(f"[ERROR] File not found: {csv_path}")
        return

    with open(csv_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Row 3 (index 2): ヘッダー行
    header_line = lines[2].strip()
    headers = header_line.split(",")

    # 日付をパース
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

    print(f"Parsed {len([d for d in dates if d])} valid dates")
    valid_dates = [d for d in dates if d]
    if valid_dates:
        print(f"Date range: {min(valid_dates)} ~ {max(valid_dates)}")

    # データ行を処理 (Row 4以降)
    result = {db_id: {} for db_id in INDICATOR_MAP.values()}
    total_upserted = 0

    for line in lines[3:]:
        line = line.strip()
        if not line or line.startswith("Data Sources") or line.startswith("Note:") or line.startswith('"Note:'):
            continue

        parts = line.split(",")
        indicator_name = parts[0].strip()

        db_indicator = INDICATOR_MAP.get(indicator_name)
        if db_indicator is None:
            continue

        for i, val_str in enumerate(parts[1:]):
            if i >= len(dates) or dates[i] is None:
                continue
            val_str = val_str.strip()
            if not val_str:
                continue
            try:
                value = float(val_str)
                # YoY: base=100形式 → %に変換
                if db_indicator == "cn_ic_yoy":
                    value = round(value, 1)  # CSVの値はすでに%形式
                else:
                    value = round(value, 2)
                result[db_indicator][dates[i]] = value
            except (ValueError, TypeError):
                continue

    for db_indicator, values in result.items():
        if not values:
            print(f"  {db_indicator}: 0 records (no data)")
            continue

        print(f"  {db_indicator}: {len(values)} records "
              f"({min(values.keys())} ~ {max(values.keys())})")

        # 先頭と末尾のデータを表示
        sorted_dates = sorted(values.keys())
        print(f"    First 3: {[(d, values[d]) for d in sorted_dates[:3]]}")
        print(f"    Last 3: {[(d, values[d]) for d in sorted_dates[-3:]]}")

        if args.dry_run:
            continue

        from services.china.nbs_db_utils import upsert_nbs_data
        count = upsert_nbs_data(db_indicator, values, source="csv")
        total_upserted += count
        print(f"    → DB upserted: {count}")

    print(f"\nTOTAL UPSERTED: {total_upserted}")
    if args.dry_run:
        print("(DRY RUN - no data was actually inserted)")


if __name__ == "__main__":
    main()
