"""
日本小売業販売額 長期時系列データインポートスクリプト

データソース: 経済産業省 商業動態統計調査
CSV:
- h2slt11j(販売額（value）(月次M)).csv - 販売額（10億円）
- h2slt11j(前年比（change）(月次M)).csv - 前年同月比（公式値、指数形式）
- h2slt51j(季調済指数(Seasonaly adjusted)（月次M）).csv - 季節調整済み指数

処理:
1. 販売額CSVから小売業計の販売額を読み込み
2. 前年比CSVから公式YoYを読み込み（指数形式→%変化に変換）
3. 季節調整済み指数CSVから前月比を計算
4. DBにUPSERT（存在すれば更新、なければ挿入）

注意:
- 前年比CSVの値は「前年=100」の指数形式（例: 101.7 = +1.7%）
- 季節調整済み指数から前月比を計算（FMP値と一致）
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import csv
from typing import List, Dict, Any, Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import SessionLocal
from sqlalchemy import text


# CSVファイルパス
CSV_DIR = Path(__file__).parent.parent / "data" / "csv_import"
VALUE_CSV = CSV_DIR / "h2slt11j(販売額（value）(月次M)).csv"
YOY_CSV = CSV_DIR / "h2slt11j(前年比（change）(月次M)).csv"
SA_INDEX_CSV = CSV_DIR / "h2slt51j(季調済指数(Seasonaly adjusted)（月次M）).csv"

# 小売業計の列インデックス（0始まり）
# 販売額CSV: T列(19) = 小売業計
# 前年比CSV: U列(20) = 小売業計
# 季調済指数CSV: T列(20) = 小売業計（Retail）
VALUE_COL = 19  # T列
YOY_COL = 20    # U列
SA_INDEX_COL = 20  # T列（季調済指数CSV）


def parse_value_csv() -> Dict[str, float]:
    """販売額CSVをパース"""
    data = {}

    if not VALUE_CSV.exists():
        print(f"Warning: Value CSV not found: {VALUE_CSV}")
        return data

    with open(VALUE_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)

        # ヘッダー行をスキップ（7行）
        for _ in range(7):
            next(reader)

        for row in reader:
            if len(row) < VALUE_COL + 1:
                continue

            year_month_str = row[1]
            if not year_month_str or '年' not in year_month_str:
                continue

            try:
                parts = year_month_str.replace('年', '-').replace('月', '')
                year, month = parts.split('-')
                date_str = f"{year}-{int(month):02d}-01"

                value = row[VALUE_COL]
                if value and value != '***':
                    data[date_str] = float(value)

            except (ValueError, IndexError):
                continue

    return data


def parse_yoy_csv() -> Dict[str, float]:
    """前年比CSVをパース（指数形式 → %変化に変換）"""
    data = {}

    if not YOY_CSV.exists():
        print(f"Warning: YoY CSV not found: {YOY_CSV}")
        return data

    with open(YOY_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)

        # ヘッダー行をスキップ（7行）
        for _ in range(7):
            next(reader)

        for row in reader:
            if len(row) < YOY_COL + 1:
                continue

            year_month_str = row[1]
            if not year_month_str or '年' not in year_month_str:
                continue

            try:
                parts = year_month_str.replace('年', '-').replace('月', '')
                year, month = parts.split('-')
                date_str = f"{year}-{int(month):02d}-01"

                value = row[YOY_COL]
                if value and value != '***':
                    # 指数形式（100=前年と同じ）を%変化に変換
                    # 例: 101.7 → +1.7%, 99.1 → -0.9%
                    index_value = float(value)
                    change_pct = round(index_value - 100, 1)
                    data[date_str] = change_pct

            except (ValueError, IndexError):
                continue

    return data


def parse_sa_index_csv() -> Dict[str, float]:
    """季節調整済み指数CSVをパース"""
    data = {}

    if not SA_INDEX_CSV.exists():
        print(f"Warning: SA Index CSV not found: {SA_INDEX_CSV}")
        return data

    with open(SA_INDEX_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)

        # ヘッダー行をスキップ（8行）
        for _ in range(8):
            next(reader)

        for row in reader:
            if len(row) < SA_INDEX_COL + 1:
                continue

            year_month_str = row[1]
            if not year_month_str:
                continue

            # 文字化けしている可能性があるので、数字を抽出
            # 形式: "2002年1月" or "2002?1?"
            try:
                # 年と月を抽出
                import re
                match = re.search(r'(\d{4})\D+(\d{1,2})', year_month_str)
                if not match:
                    continue

                year = int(match.group(1))
                month = int(match.group(2))
                date_str = f"{year}-{month:02d}-01"

                value = row[SA_INDEX_COL]
                if value and value != '***':
                    data[date_str] = float(value)

            except (ValueError, IndexError):
                continue

    return data


def calculate_mom_from_sa_index(sa_index: Dict[str, float]) -> Dict[str, float]:
    """季節調整済み指数から前月比を計算"""
    mom_changes = {}
    dates = sorted(sa_index.keys())

    for i, date_str in enumerate(dates):
        if i == 0:
            continue  # 最初の月は前月がないのでスキップ

        current_value = sa_index[date_str]
        prev_date = dates[i - 1]
        prev_value = sa_index[prev_date]

        if prev_value and prev_value != 0:
            # 前月比を計算（%）
            mom_pct = round((current_value - prev_value) / prev_value * 100, 1)
            mom_changes[date_str] = mom_pct

    return mom_changes


def merge_data(
    values: Dict[str, float],
    yoy_changes: Dict[str, float],
    mom_changes: Dict[str, float]
) -> List[Dict[str, Any]]:
    """3つのデータソースをマージ"""
    # 全日付を収集
    all_dates = set(values.keys()) | set(yoy_changes.keys()) | set(mom_changes.keys())

    result = []
    for date_str in sorted(all_dates):
        result.append({
            'date': date_str,
            'sales_amount': values.get(date_str),
            'yoy_change': yoy_changes.get(date_str),
            'mom_change': mom_changes.get(date_str),
        })

    return result


def upsert_to_db(data: List[Dict[str, Any]]) -> int:
    """データをDBにUPSERT"""
    with SessionLocal() as session:
        count = 0

        for item in data:
            # 少なくとも1つのデータがある場合のみ挿入
            if item['sales_amount'] is None and item['yoy_change'] is None and item['mom_change'] is None:
                continue

            session.execute(
                text("""
                    INSERT INTO jp_retail_sales_history (date, sales_amount, yoy_change, mom_change, source)
                    VALUES (:date, :sales_amount, :yoy_change, :mom_change, 'meti')
                    ON CONFLICT (date) DO UPDATE SET
                        sales_amount = COALESCE(EXCLUDED.sales_amount, jp_retail_sales_history.sales_amount),
                        yoy_change = COALESCE(EXCLUDED.yoy_change, jp_retail_sales_history.yoy_change),
                        mom_change = COALESCE(EXCLUDED.mom_change, jp_retail_sales_history.mom_change),
                        source = 'meti',
                        updated_at = NOW()
                """),
                {
                    'date': item['date'],
                    'sales_amount': item['sales_amount'],
                    'yoy_change': item['yoy_change'],
                    'mom_change': item['mom_change'],
                }
            )
            count += 1

        session.commit()

    return count


def main():
    """メイン処理"""
    print("=" * 60)
    print("Japan Retail Sales History Import")
    print("=" * 60)

    # 販売額CSV読み込み
    print(f"\nReading Value CSV: {VALUE_CSV}")
    values = parse_value_csv()
    print(f"  Loaded {len(values)} records")

    # 前年比CSV読み込み
    print(f"\nReading YoY CSV: {YOY_CSV}")
    yoy_changes = parse_yoy_csv()
    print(f"  Loaded {len(yoy_changes)} records")

    # 季節調整済み指数CSV読み込み
    print(f"\nReading SA Index CSV: {SA_INDEX_CSV}")
    sa_index = parse_sa_index_csv()
    print(f"  Loaded {len(sa_index)} records")

    # 季節調整済み指数から前月比を計算
    print("\nCalculating MoM from SA Index...")
    mom_changes = calculate_mom_from_sa_index(sa_index)
    print(f"  Calculated {len(mom_changes)} MoM records")

    # データマージ
    print("\nMerging data...")
    merged_data = merge_data(values, yoy_changes, mom_changes)
    print(f"  Total {len(merged_data)} records")

    if not merged_data:
        print("No data found")
        return

    # 範囲を表示
    print(f"\nDate range: {merged_data[0]['date']} to {merged_data[-1]['date']}")

    # サンプル表示
    print("\nSample data (latest 10):")
    for item in merged_data[-10:]:
        sales = f"{item['sales_amount']:.0f}" if item['sales_amount'] else "N/A"
        yoy = f"{item['yoy_change']:+.1f}%" if item['yoy_change'] is not None else "N/A"
        mom = f"{item['mom_change']:+.1f}%" if item['mom_change'] is not None else "N/A"
        print(f"  {item['date']}: {sales}億円, YoY={yoy}, MoM={mom}")

    # DBにインポート
    print("\nImporting to database...")
    count = upsert_to_db(merged_data)
    print(f"Imported {count} records to jp_retail_sales_history")

    # 確認
    with SessionLocal() as session:
        result = session.execute(text("SELECT COUNT(*) FROM jp_retail_sales_history")).scalar()
        print(f"Total records in DB: {result}")

    print("\n" + "=" * 60)
    print("Import completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
