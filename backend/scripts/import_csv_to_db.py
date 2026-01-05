"""
CSVファイルからeconomic_calendar_eventsテーブルへ過去データをインポートするスクリプト

FMPは直近1年分しか取得できないため、それ以前のデータをCSVから補填する。
既存データ（FMPからの取得分）は上書きせず、存在しない日付のみ追加する。

対象指標:
- ISM製造業景況指数 (ISM Manufacturing PMI)
- ISM非製造業景況指数 (ISM Services PMI)
- CB消費者信頼感指数 (CB Consumer Confidence)
- チャレンジャー人員削減数 (Challenger Job Cuts)
- レッドブック (Redbook YoY)
- コントロールグループ (Retail Sales Control Group MoM)
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .envファイルを読み込み（プロジェクトルートの親ディレクトリ）
env_path = project_root.parent / ".env"
load_dotenv(env_path)

from core.database import get_db_connection

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# CSVファイルと指標のマッピング
CSV_CONFIGS = [
    {
        "file": "ISM製造業景況指数.csv",
        "event_name": "ISM Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "High",
        "date_format": "monthly",  # 2010/1 形式
        "value_type": "number",
    },
    {
        "file": "ISM非製造業景況指数.csv",
        "event_name": "ISM Services PMI",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "number",
    },
    {
        "file": "CB消費者信頼感指数.csv",
        "event_name": "CB Consumer Confidence",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "number",
    },
    {
        "file": "チャレンジャー人員削減数.csv",
        "event_name": "Challenger Job Cuts",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "number",
        "unit": "K",
    },
    {
        "file": "レッドブック（前年比）.csv",
        "event_name": "Redbook YoY",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Low",
        "date_format": "daily",  # 2015年01月06日 形式
        "value_type": "percent",
    },
    {
        "file": "コントロールグループ.csv",
        "event_name": "Retail Sales Control Group MoM",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "percent",
    },
]


def parse_date_monthly(date_str: str, time_str: str) -> datetime:
    """
    月次データの日付をパース (2010/1 形式)
    時間は JST として解釈し、UTC に変換
    """
    year, month = date_str.split("/")
    year = int(year)
    month = int(month)

    # 時間をパース
    hour, minute = 0, 0
    if time_str and ":" in time_str:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

    # JST で作成し UTC に変換
    dt_jst = datetime(year, month, 1, hour, minute, tzinfo=JST)
    return dt_jst.astimezone(UTC)


def parse_date_daily(date_str: str, time_str: str) -> datetime:
    """
    日次データの日付をパース (2015年01月06日 形式)
    時間は JST として解釈し、UTC に変換
    """
    # 2015年01月06日 → 2015-01-06
    date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "")
    parts = date_str.split("-")
    year = int(parts[0])
    month = int(parts[1])
    day = int(parts[2])

    # 時間をパース
    hour, minute = 0, 0
    if time_str and ":" in time_str:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

    # JST で作成し UTC に変換
    dt_jst = datetime(year, month, day, hour, minute, tzinfo=JST)
    return dt_jst.astimezone(UTC)


def parse_value(value_str, value_type: str) -> float:
    """値をパース（%を除去など）"""
    if pd.isna(value_str) or value_str == "" or value_str is None:
        return None

    value_str = str(value_str).strip()
    if value_type == "percent":
        value_str = value_str.replace("%", "")

    try:
        return float(value_str)
    except (ValueError, TypeError):
        return None


def get_existing_dates(conn, event_pattern: str) -> set:
    """既存データの日付を取得"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT datetime_utc::date
            FROM economic_calendar_events
            WHERE country = 'US'
              AND event ILIKE %s
        """, (f"%{event_pattern}%",))
        return {row[0] for row in cur.fetchall()}


def import_csv(config: dict, csv_dir: Path, dry_run: bool = False) -> dict:
    """CSVファイルをDBにインポート"""
    file_path = csv_dir / config["file"]

    if not file_path.exists():
        return {"status": "skip", "reason": f"File not found: {file_path}"}

    print(f"\n{'='*60}")
    print(f"Processing: {config['event_name']}")
    print(f"File: {file_path}")
    print(f"{'='*60}")

    # CSV読み込み
    df = pd.read_csv(file_path, encoding="utf-8")
    print(f"Total rows in CSV: {len(df)}")

    # 既存データの日付を取得
    with get_db_connection() as conn:
        existing_dates = get_existing_dates(conn, config["event_name"])
        print(f"Existing dates in DB: {len(existing_dates)}")

        inserted = 0
        skipped = 0
        errors = 0

        with conn.cursor() as cur:
            for _, row in df.iterrows():
                try:
                    # 日付をパース
                    date_str = str(row["公表日"])
                    time_str = str(row["時間"]) if "時間" in row else ""

                    if config["date_format"] == "monthly":
                        dt_utc = parse_date_monthly(date_str, time_str)
                    else:
                        dt_utc = parse_date_daily(date_str, time_str)

                    # 既存チェック
                    if dt_utc.date() in existing_dates:
                        skipped += 1
                        continue

                    # 値をパース
                    actual = parse_value(row["結果"], config["value_type"])
                    estimate = parse_value(row.get("予想"), config["value_type"])
                    previous = parse_value(row.get("前回"), config["value_type"])

                    if actual is None:
                        skipped += 1
                        continue

                    # 期間ラベルを生成
                    if config["date_format"] == "monthly":
                        period_label = dt_utc.strftime("%b")  # Jan, Feb, etc.
                    else:
                        period_label = None

                    # event_key を生成
                    event_key = f"{config['event_name']}_{dt_utc.strftime('%Y%m%d')}"

                    if dry_run:
                        print(f"  [DRY RUN] Would insert: {dt_utc.date()} - {actual}")
                        inserted += 1
                        continue

                    # DBに挿入
                    cur.execute("""
                        INSERT INTO economic_calendar_events (
                            provider, event_key, country, currency, event, event_period,
                            datetime_raw, datetime_utc, has_time, impact,
                            previous, estimate, actual, raw_json
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s
                        )
                        ON CONFLICT (provider, event_key) DO NOTHING
                    """, (
                        config["provider"],
                        event_key,
                        config["country"],
                        config["currency"],
                        config["event_name"],
                        period_label,
                        dt_utc.isoformat(),
                        dt_utc,
                        True if time_str else False,
                        config["impact"],
                        previous,
                        estimate,
                        actual,
                        "{}",
                    ))
                    inserted += 1

                except Exception as e:
                    print(f"  Error processing row: {row.to_dict()} - {e}")
                    errors += 1

            if not dry_run:
                conn.commit()

        result = {
            "status": "success",
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }
        print(f"Result: {result}")
        return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import CSV data to economic_calendar_events table")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert data")
    parser.add_argument("--indicator", type=str, help="Only import specific indicator (e.g., 'ISM Manufacturing')")
    args = parser.parse_args()

    # CSVファイルのディレクトリ（backend/data/csv_import）
    csv_dir = Path(__file__).parent.parent / "data" / "csv_import"

    print(f"CSV Directory: {csv_dir}")
    print(f"Dry Run: {args.dry_run}")

    results = {}

    for config in CSV_CONFIGS:
        if args.indicator and args.indicator.lower() not in config["event_name"].lower():
            continue

        result = import_csv(config, csv_dir, dry_run=args.dry_run)
        results[config["event_name"]] = result

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    total_inserted = 0
    total_skipped = 0
    total_errors = 0

    for event_name, result in results.items():
        print(f"{event_name}:")
        print(f"  Status: {result.get('status')}")
        if result.get("status") == "success":
            print(f"  Inserted: {result.get('inserted')}")
            print(f"  Skipped: {result.get('skipped')}")
            print(f"  Errors: {result.get('errors')}")
            total_inserted += result.get("inserted", 0)
            total_skipped += result.get("skipped", 0)
            total_errors += result.get("errors", 0)
        else:
            print(f"  Reason: {result.get('reason')}")

    print(f"\nTotal: Inserted={total_inserted}, Skipped={total_skipped}, Errors={total_errors}")


if __name__ == "__main__":
    main()
