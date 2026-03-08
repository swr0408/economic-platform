"""
NBS PMI CSVファイルからnbs_monthly_dataテーブルへ過去データをインポート

CSVは転置ワイド形式（行=指標、列=月）:
  Row 1: Database:Monthly
  Row 2: Month:2010-
  Row 3: Indicators,Feb. 2026,Jan. 2026,...
  Row 4+: データ行

3ファイルを処理:
  - 中国国家統計局製造業PMI.csv     → 製造業PMI + サブインデックス
  - 中国国家統計局非製造業PMI.csv   → 非製造業PMI + サブインデックス
  - 中国国家統計局総合PMI.csv       → 総合PMI
"""
import sys
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
env_path = project_root.parent / ".env"
load_dotenv(env_path)


# ---------------------------------------------------------------------------
# CSV指標名 → DB指標IDマッピング
# ---------------------------------------------------------------------------
MANUFACTURING_MAP = {
    "Manufacturing Purchasing Managers' Index(%)": "cn_pmi_manufacturing",
    "Production index(%)": "cn_pmi_mfg_production",
    "New orders index(%)": "cn_pmi_mfg_new_orders",
    "New export orders index(%)": "cn_pmi_mfg_new_export_orders",
    "In hand Orders Index(%)": "cn_pmi_mfg_in_hand_orders",
    "Employment index(%)": "cn_pmi_mfg_employment",
    "Main raw material purchase price index(%)": "cn_pmi_mfg_raw_material_price",
    "Producer prices index(%)": "cn_pmi_mfg_producer_prices",
    "Supplier delivery time index(%)": "cn_pmi_mfg_supplier_delivery",
}

NON_MANUFACTURING_MAP = {
    "Non-Manufacturing Business Index(%)": "cn_pmi_non_manufacturing",
    "Services PMI?Seasonlly Adjusted?(%)": "cn_pmi_nmf_services",
    "Construction PMI?Seasonlly Adjusted?(%)": "cn_pmi_nmf_construction",
    "New orders index(%)": "cn_pmi_nmf_new_orders",
    "New export orders index(%)": "cn_pmi_nmf_export_new_orders",
    "In hand Orders Index(%)": "cn_pmi_nmf_in_hand_orders",
    "Charge price index(%)": "cn_pmi_nmf_sale_price",
    "Intermediate input price index(%)": "cn_pmi_nmf_input_price",
    "Supplier delivery time index(%)": "cn_pmi_nmf_supplier_delivery",
    "Employment index(%)": "cn_pmi_nmf_employment",
}

COMPOSITE_MAP = {
    "Comprehensive PMI output index(%)": "cn_pmi_composite",
}


def parse_date_header(header: str) -> str:
    """CSVヘッダーの月表記を YYYY-MM-01 形式に変換

    対応形式:
    - "Feb. 2026" → "2026-02-01"
    - "Jun 2025"  → "2025-06-01"
    - "June 2020" → "2020-06-01"
    - "Oct2012"   → "2012-10-01"  (スペースなし)
    - "Jun2012"   → "2012-06-01"  (スペースなし)
    """
    header = header.strip()

    MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4,
        "june": 6, "july": 7, "august": 8, "september": 9,
        "october": 10, "november": 11, "december": 12,
    }

    # "Feb. 2026", "Jun 2025", "June 2020" パターン
    m = re.match(r"([A-Za-z]+)\.?\s*(\d{4})", header)
    if m:
        month_str = m.group(1).lower()
        year = int(m.group(2))
        month = MONTH_MAP.get(month_str)
        if month:
            return f"{year}-{month:02d}-01"

    raise ValueError(f"Cannot parse date header: '{header}'")


def parse_csv_transposed(file_path: Path, indicator_map: dict) -> dict:
    """転置ワイド形式CSVを解析

    Returns:
        {db_indicator: {date_str: value, ...}, ...}
    """
    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Row 3 (index 2): ヘッダー行
    header_line = lines[2].strip()
    headers = header_line.split(",")
    # headers[0] = "Indicators", headers[1:] = 月名

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

    # データ行を処理 (Row 4以降)
    result = {db_id: {} for db_id in indicator_map.values()}

    for line in lines[3:]:
        line = line.strip()
        if not line or line.startswith("Data Sources") or line.startswith("Note:"):
            continue

        parts = line.split(",")
        indicator_name = parts[0].strip()

        # マッピング検索
        db_indicator = indicator_map.get(indicator_name)
        if db_indicator is None:
            continue

        # 値をパース
        for i, val_str in enumerate(parts[1:]):
            if i >= len(dates) or dates[i] is None:
                continue
            val_str = val_str.strip()
            if not val_str:
                continue
            try:
                value = float(val_str)
                result[db_indicator][dates[i]] = value
            except (ValueError, TypeError):
                continue

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import NBS PMI CSV data to nbs_monthly_data table")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert data")
    args = parser.parse_args()

    csv_dir = Path(__file__).parent.parent / "data" / "csv_import"

    files = [
        ("中国国家統計局製造業PMI.csv", MANUFACTURING_MAP),
        ("中国国家統計局非製造業PMI.csv", NON_MANUFACTURING_MAP),
        ("中国国家統計局総合PMI.csv", COMPOSITE_MAP),
    ]

    total_upserted = 0

    for filename, indicator_map in files:
        file_path = csv_dir / filename
        if not file_path.exists():
            print(f"[SKIP] File not found: {file_path}")
            continue

        print(f"\n{'='*60}")
        print(f"Processing: {filename}")
        print(f"{'='*60}")

        data = parse_csv_transposed(file_path, indicator_map)

        for db_indicator, values in data.items():
            if not values:
                print(f"  {db_indicator}: 0 records (no data)")
                continue

            print(f"  {db_indicator}: {len(values)} records "
                  f"({min(values.keys())} ~ {max(values.keys())})")

            if args.dry_run:
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
