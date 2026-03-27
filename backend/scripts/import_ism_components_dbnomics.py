"""
ISM Components: DBnomics APIからの過去データをDBに初回投入

DBnomics APIから製造業・非製造業の全サブインデックスを取得し、
ism_components テーブルに一括投入する。

Usage:
    cd backend
    python scripts/import_ism_components_dbnomics.py
    python scripts/import_ism_components_dbnomics.py --dry-run
"""
import sys
import requests
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
env_path = project_root.parent / ".env"
load_dotenv(env_path)


# DBnomics API
DBNOMICS_BASE_URL = "https://api.db.nomics.world/v22"

# 製造業シリーズ
MANUFACTURING_SERIES = {
    "new_orders": "ISM/neword/in",
    "production": "ISM/production/in",
    "employment": "ISM/employment/in",
    "supplier_deliveries": "ISM/supdel/in",
    "prices": "ISM/prices/in",
    "inventories": "ISM/inventories/in",
}

# 非製造業シリーズ
NON_MANUFACTURING_SERIES = {
    "new_orders": "ISM/nm-neword/in",
    "business_activity": "ISM/nm-busact/in",
    "employment": "ISM/nm-employment/in",
    "supplier_deliveries": "ISM/nm-supdel/in",
    "prices": "ISM/nm-prices/in",
    "inventories": "ISM/nm-inventories/in",
}


def fetch_series(series_code: str) -> dict:
    """DBnomics APIから1シリーズを取得

    Returns:
        {period: value, ...}  e.g. {"2020-01": 52.4}
    """
    url = f"{DBNOMICS_BASE_URL}/series/{series_code}?observations=1&format=json"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    series = data.get("series", {})
    docs = series.get("docs", [])
    if not docs:
        return {}

    doc = docs[0]
    periods = doc.get("period", [])
    values = doc.get("value", [])

    if len(periods) != len(values):
        return {}

    result = {}
    for i, period in enumerate(periods):
        value = values[i]
        if value is not None and not (isinstance(value, float) and value != value):
            result[str(period)] = float(value)

    return result


def combine_series(series_map: dict, type_label: str) -> list:
    """複数シリーズを取得・統合してレコードリストを返す"""
    all_series = {}
    for field_name, series_code in series_map.items():
        print(f"  Fetching {field_name} ({series_code})...")
        data = fetch_series(series_code)
        print(f"    → {len(data)} records")
        all_series[field_name] = data

    # 全期間を収集
    all_periods = set()
    for data in all_series.values():
        all_periods.update(data.keys())

    # 統合
    records = []
    for period in sorted(all_periods):
        record = {"date": f"{period}-01"}
        has_data = False
        for field_name in series_map.keys():
            val = all_series.get(field_name, {}).get(period)
            record[field_name] = val
            if val is not None:
                has_data = True
        if has_data:
            records.append(record)

    return records


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import ISM Components from DBnomics to DB")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert data")
    args = parser.parse_args()

    # --- 製造業 ---
    print(f"\n{'='*60}")
    print("ISM Manufacturing Components")
    print(f"{'='*60}")
    mfg_records = combine_series(MANUFACTURING_SERIES, "manufacturing")
    print(f"\nTotal: {len(mfg_records)} records")
    if mfg_records:
        print(f"Range: {mfg_records[0]['date']} ~ {mfg_records[-1]['date']}")

    # --- 非製造業 ---
    print(f"\n{'='*60}")
    print("ISM Non-Manufacturing Components")
    print(f"{'='*60}")
    nm_records = combine_series(NON_MANUFACTURING_SERIES, "non_manufacturing")
    print(f"\nTotal: {len(nm_records)} records")
    if nm_records:
        print(f"Range: {nm_records[0]['date']} ~ {nm_records[-1]['date']}")

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN - no data was inserted")
        print(f"Would insert: {len(mfg_records)} manufacturing + {len(nm_records)} non-manufacturing")
        print(f"{'='*60}")
        return

    # DB投入
    from services.usa.ism_components_db_utils import upsert_ism_components

    print(f"\n{'='*60}")
    print("Inserting to DB...")
    print(f"{'='*60}")

    mfg_count = upsert_ism_components("manufacturing", mfg_records, source="dbnomics")
    print(f"Manufacturing: {mfg_count} records upserted")

    nm_count = upsert_ism_components("non_manufacturing", nm_records, source="dbnomics")
    print(f"Non-Manufacturing: {nm_count} records upserted")

    print(f"\nTOTAL: {mfg_count + nm_count} records")


if __name__ == "__main__":
    main()
