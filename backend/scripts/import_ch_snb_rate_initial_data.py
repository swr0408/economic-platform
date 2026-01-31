"""
スイス政策金利（SNB Interest Rate Decision）初回データ取込スクリプト

CSVファイルからSNB政策金利の過去データをDBに格納

使用方法:
    cd backend
    python scripts/import_ch_snb_rate_initial_data.py

データソース:
- CSV: backend/data/csv_import/スイス 政策金利発表.csv
"""
import sys
import os
import csv
from datetime import datetime
from typing import Dict, List, Any

# パスを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .envをロード
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

from core.database import get_db_connection

# CSVファイルパス
CSV_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "csv_import", "スイス 政策金利発表.csv"
)

# FMPイベント名（economic_calendar_eventsテーブルで使用）
FMP_EVENT_NAME = "SNB Interest Rate Decision"


def parse_csv_date(date_str: str) -> str:
    """
    CSVの日付形式(YYYY.MM.DD)をISO形式(YYYY-MM-DD)に変換
    """
    try:
        parts = date_str.strip().split('.')
        if len(parts) == 3:
            year, month, day = parts
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except Exception:
        pass
    return date_str


def load_csv_data() -> List[Dict[str, Any]]:
    """CSVファイルからデータを読み込む"""
    result = []

    if not os.path.exists(CSV_FILE):
        print(f"Error: CSV file not found: {CSV_FILE}")
        return result

    print(f"Loading CSV file: {CSV_FILE}")

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                # 日付を変換
                date_str = parse_csv_date(row.get('公表日', ''))
                if not date_str:
                    continue

                # 結果（実際の値）
                actual_str = row.get('結果', '').strip()
                if not actual_str:
                    continue

                actual = float(actual_str)

                # 予想（オプション）
                estimate_str = row.get('予想', '').strip()
                estimate = float(estimate_str) if estimate_str else None

                # 前回（オプション）
                previous_str = row.get('前回', '').strip()
                previous = float(previous_str) if previous_str else None

                result.append({
                    "date": date_str,
                    "actual": actual,
                    "estimate": estimate,
                    "previous": previous,
                })

            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping row due to error: {e}")
                continue

    # 日付でソート
    result.sort(key=lambda x: x["date"])
    print(f"Loaded {len(result)} records from CSV")

    if result:
        print(f"Date range: {result[0]['date']} to {result[-1]['date']}")
        print(f"Latest: {result[-1]}")

    return result


def import_to_database(data: List[Dict[str, Any]]):
    """データをDBにインポート（economic_calendar_eventsテーブル）"""
    import hashlib
    import json as json_module

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            insert_count = 0
            update_count = 0
            skip_count = 0

            for record in data:
                # 日付をdatetimeに変換（UTC 07:30に設定、SNBは通常8:30 CETに発表）
                datetime_utc = datetime.strptime(record["date"], "%Y-%m-%d").replace(hour=7, minute=30)
                datetime_raw = datetime_utc.strftime("%Y-%m-%d %H:%M:%S")

                # event_keyを生成（重複防止用ハッシュ）
                event_key = hashlib.md5(
                    f"CSV:CH:{FMP_EVENT_NAME}:{datetime_raw}".encode()
                ).hexdigest()

                # 既存レコードをチェック
                cursor.execute("""
                    SELECT id, actual FROM economic_calendar_events
                    WHERE country = 'CH'
                      AND event ILIKE %s
                      AND DATE(datetime_utc) = %s
                """, (f"%{FMP_EVENT_NAME}%", record["date"]))

                existing = cursor.fetchone()

                if existing:
                    existing_id, existing_actual = existing
                    if existing_actual is None:
                        # 既存レコードのactualがNULLの場合は更新
                        cursor.execute("""
                            UPDATE economic_calendar_events
                            SET actual = %s,
                                estimate = COALESCE(%s, estimate),
                                previous = COALESCE(%s, previous),
                                updated_at = NOW()
                            WHERE id = %s
                        """, (record["actual"], record["estimate"], record["previous"], existing_id))
                        update_count += 1
                    else:
                        # 既にactualが設定されている場合はスキップ
                        skip_count += 1
                else:
                    # raw_jsonを作成
                    raw_json = json_module.dumps({
                        "source": "csv_import",
                        "date": record["date"],
                        "actual": record["actual"],
                        "estimate": record["estimate"],
                        "previous": record["previous"],
                    })

                    # 新規レコードを挿入
                    cursor.execute("""
                        INSERT INTO economic_calendar_events (
                            provider, event_key, country, event, datetime_raw, datetime_utc,
                            has_time, impact, actual, estimate, previous, raw_json
                        ) VALUES (
                            'CSV', %s, 'CH', %s, %s, %s, TRUE, 'High', %s, %s, %s, %s
                        )
                        ON CONFLICT (provider, event_key) DO NOTHING
                    """, (
                        event_key,
                        FMP_EVENT_NAME,
                        datetime_raw,
                        datetime_utc,
                        record["actual"],
                        record["estimate"],
                        record["previous"],
                        raw_json,
                    ))
                    if cursor.rowcount > 0:
                        insert_count += 1
                    else:
                        skip_count += 1

            conn.commit()
            cursor.close()

            print(f"\nDatabase import completed:")
            print(f"  - Inserted: {insert_count} records")
            print(f"  - Updated: {update_count} records")
            print(f"  - Skipped: {skip_count} records (already existed or had actual value)")

    except Exception as e:
        print(f"Error importing to database: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("=" * 60)
    print("Switzerland SNB Interest Rate Decision - Initial Data Import")
    print("=" * 60)

    # CSVからデータを読み込む
    print("\n--- Loading CSV data ---")
    data = load_csv_data()

    if not data:
        print("\nError: No data loaded from CSV")
        return

    # DBにインポート
    print("\n--- Importing to database ---")
    import_to_database(data)

    print("\n" + "=" * 60)
    print("Import completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
