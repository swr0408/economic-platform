"""
NBS 貿易収支 CSVファイルからnbs_monthly_dataテーブルへ過去データをインポート

CSVは転置ワイド形式（行=指標、列=月）— import_nbs_pmi_csv.py と同じ形式。

ファイル: 中国貿易収支.csv

取り込む系列:
  - cn_trade_balance        : 貿易収支（1000 USD → 億 USD）
  - cn_exports              : 輸出額（1000 USD → 億 USD）
  - cn_imports              : 輸入額（1000 USD → 億 USD）
  - cn_exports_yoy          : 輸出 前年比 (%)
  - cn_imports_yoy          : 輸入 前年比 (%)
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
env_path = project_root.parent / ".env"
load_dotenv(env_path)

# import_nbs_pmi_csv の共通関数を再利用
from scripts.import_nbs_pmi_csv import parse_csv_transposed, parse_date_header  # noqa: E402

# ---------------------------------------------------------------------------
# CSV指標名 → DB指標IDマッピング
# ---------------------------------------------------------------------------
TRADE_MAP = {
    "Balance of Imports and Exports Current Period(1000 US dollars)": "cn_trade_balance",
    "Total Value of Exports Current Period(1000 US dollars)": "cn_exports",
    "Total Value of Imports Current Period(1000 US dollars)": "cn_imports",
    "Total Value of Exports Growth Rate (The same period last year=100)(%)": "cn_exports_yoy",
    "Total Value of Imports Growth Rate (The same period last year=100)(%)": "cn_imports_yoy",
}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import NBS Trade Balance CSV data to nbs_monthly_data table")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert data")
    args = parser.parse_args()

    csv_dir = Path(__file__).parent.parent / "data" / "csv_import"
    file_path = csv_dir / "中国貿易収支.csv"

    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return

    print(f"\n{'='*60}")
    print(f"Processing: 中国貿易収支.csv")
    print(f"{'='*60}")

    data = parse_csv_transposed(file_path, TRADE_MAP)

    # 貿易収支・輸出・輸入は1000 USD → 億 USD変換
    LEVEL_INDICATORS = {"cn_trade_balance", "cn_exports", "cn_imports"}

    total_upserted = 0

    for db_indicator, values in data.items():
        if not values:
            print(f"  {db_indicator}: 0 records (no data)")
            continue

        # レベル指標は1000 USD → 億 USDに変換
        if db_indicator in LEVEL_INDICATORS:
            values = {k: round(v / 100_000, 2) for k, v in values.items()}

        print(f"  {db_indicator}: {len(values)} records "
              f"({min(values.keys())} ~ {max(values.keys())})")

        if args.dry_run:
            # サンプル表示
            sorted_dates = sorted(values.keys())
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
