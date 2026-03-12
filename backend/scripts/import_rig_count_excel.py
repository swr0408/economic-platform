"""
Baker Hughes リグカウント Excel データを DB にインポートするスクリプト

データソース:
  - Historical (1987-2024): XLSB形式, "US Oil & Gas Split" シート
    URL: https://rigcount.bakerhughes.com/static-files/48162dfc-eb21-4612-8b01-72743e3ed420
    Row 6: ヘッダー (Date, Oil, Gas, Misc, Total, % Oil, % Gas)
    Row 7+: データ (Date=Excelシリアル日付, Oil=リグ数)

  - Recent (2024-2026): XLSX形式, "NAM Weekly" シート
    URL: https://rigcount.bakerhughes.com/static-files/c5f2ec8e-8dc5-41f3-8d64-8b3ad10b2b0d
    巨大ファイル（188K行）→ 代替: Historicalファイルで2024/03まで取得し、FMPが以降を補完

使い方:
  cd backend
  python scripts/import_rig_count_excel.py

注意:
  - Historical file は XLSB形式 → pyxlsb を使用
  - ローカルファイルがあればダウンロードをスキップ
  - 既存データ（FMPからの取得分）は上書きしない
"""
import sys
import io
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .envファイルを読み込み
env_path = project_root.parent / ".env"
load_dotenv(env_path)

from core.database import get_db_connection

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# Baker Hughes Excel URLs (変更される可能性あり)
HISTORICAL_URL = "https://rigcount.bakerhughes.com/static-files/48162dfc-eb21-4612-8b01-72743e3ed420"
RECENT_URL = "https://rigcount.bakerhughes.com/static-files/c5f2ec8e-8dc5-41f3-8d64-8b3ad10b2b0d"

# ローカルファイルがあればそちらを使用（ダウンロードが遅い場合用）
LOCAL_FILE_HISTORICAL = project_root / "data" / "csv_import" / "baker_hughes_historical.xlsx"
LOCAL_FILE_RECENT = project_root / "data" / "csv_import" / "baker_hughes_recent.xlsx"

EVENT_NAME = "Baker Hughes Oil Rig Count"
PROVIDER = "CSV_IMPORT"
COUNTRY = "US"
CURRENCY = "USD"
IMPACT = "Medium"

# Excel serial date epoch (1900-01-01, but Excel incorrectly counts 1900-02-29)
EXCEL_EPOCH = datetime(1899, 12, 30)


def excel_serial_to_date(serial: float) -> str:
    """Excelシリアル日付 → YYYY-MM-DD 文字列"""
    dt = EXCEL_EPOCH + timedelta(days=int(serial))
    return dt.strftime("%Y-%m-%d")


def download_or_load(url: str, local_path: Path) -> bytes:
    """ローカルファイルがあればそちらを使い、なければダウンロード"""
    if local_path.exists():
        print(f"  Using local file: {local_path}")
        return local_path.read_bytes()

    print(f"  Downloading from {url} (this may take a while)...")
    resp = requests.get(url, timeout=300, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    if resp.status_code != 200:
        raise RuntimeError(f"Download failed: HTTP {resp.status_code}")
    print(f"  Downloaded {len(resp.content):,} bytes")

    # ローカルに保存
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(resp.content)
    print(f"  Saved to {local_path}")

    return resp.content


def parse_historical_xlsb(content: bytes) -> list:
    """Historical XLSB (US Oil & Gas Split シート) をパース"""
    from pyxlsb import open_workbook

    # pyxlsb は file path を受け付ける
    import tempfile
    tmp_path = None
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsb", delete=False)
    tmp_path = tmp.name
    tmp.write(content)
    tmp.close()

    try:
        wb = open_workbook(tmp_path)
        print(f"  Sheets: {wb.sheets}")

        target_sheet = None
        for name in wb.sheets:
            if "oil" in name.lower() and "gas" in name.lower() and "split" in name.lower():
                if "us" in name.lower() or "U" in name:
                    target_sheet = name
                    break
        if not target_sheet:
            # US Oil & Gas Splitを探す
            for name in wb.sheets:
                if "US Oil" in name:
                    target_sheet = name
                    break
        if not target_sheet:
            raise RuntimeError(f"Sheet not found. Available: {wb.sheets}")

        print(f"  Using sheet: '{target_sheet}'")

        with wb.get_sheet(target_sheet) as ws:
            all_rows = list(ws.rows())

        print(f"  Total rows: {len(all_rows)}")

        # ヘッダー行を探す (Row 6: Date, Oil, Gas, Misc, Total, % Oil, % Gas)
        header_row_idx = None
        date_col = None
        oil_col = None

        for i in range(min(15, len(all_rows))):
            row = all_rows[i]
            for j, cell in enumerate(row):
                if cell.v is not None:
                    val_str = str(cell.v).strip().lower()
                    if val_str == "date":
                        date_col = j
                        header_row_idx = i
                    elif val_str == "oil":
                        oil_col = j
            if date_col is not None and oil_col is not None:
                break

        if date_col is None or oil_col is None:
            print("  Could not find Date/Oil columns. First rows:")
            for i in range(min(10, len(all_rows))):
                vals = [str(c.v)[:20] if c.v else "" for c in all_rows[i][:10]]
                print(f"    Row {i}: {vals}")
            raise RuntimeError("Could not find Date and Oil columns")

        print(f"  Header at row {header_row_idx}: Date=col {date_col}, Oil=col {oil_col}")

        records = []
        for i in range(header_row_idx + 1, len(all_rows)):
            row = all_rows[i]
            if len(row) <= max(date_col, oil_col):
                continue

            date_val = row[date_col].v
            oil_val = row[oil_col].v

            if date_val is None or oil_val is None:
                continue

            # Date: Excelシリアル日付 (float)
            try:
                serial = float(date_val)
                date_str = excel_serial_to_date(serial)
            except (ValueError, TypeError):
                # 文字列の場合
                if isinstance(date_val, str):
                    for fmt in ["%Y-%m-%d", "%m/%d/%Y"]:
                        try:
                            dt = datetime.strptime(date_val.strip(), fmt)
                            date_str = dt.strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            continue
                    else:
                        continue
                else:
                    continue

            # Oil value
            try:
                rig_count = int(float(oil_val))
            except (ValueError, TypeError):
                continue

            if rig_count <= 0:
                continue

            records.append({"date": date_str, "value": rig_count})

        print(f"  Parsed {len(records)} records from historical data")
        if records:
            print(f"  Range: {records[0]['date']} ~ {records[-1]['date']}")
        return records

    finally:
        import os
        if tmp_path:
            try:
                wb.close()
            except Exception:
                pass
            try:
                os.unlink(tmp_path)
            except PermissionError:
                pass  # Windows: file still locked, will be cleaned up later


def parse_recent_xlsx(local_path: Path) -> list:
    """Recent XLSX (NAM Weekly シート) をpandasでパース
    Country=UNITED STATES, DrillFor=Oil でフィルタし、US_PublishDateごとに合計
    """
    import pandas as pd

    print(f"  Reading {local_path} with pandas...")
    df = pd.read_excel(local_path, sheet_name="NAM Weekly", header=10, engine="openpyxl")
    print(f"  Shape: {df.shape}, Columns: {df.columns.tolist()}")

    # Filter: UNITED STATES + Oil
    us_oil = df[(df["Country"] == "UNITED STATES") & (df["DrillFor"] == "Oil")]
    print(f"  US Oil rows: {len(us_oil)}")

    # Group by US_PublishDate and sum Rig Count Value
    grouped = us_oil.groupby("US_PublishDate")["Rig Count Value"].sum().reset_index()
    grouped = grouped.sort_values("US_PublishDate")

    records = []
    for _, row in grouped.iterrows():
        date_val = row["US_PublishDate"]
        value = int(row["Rig Count Value"])

        if hasattr(date_val, "strftime"):
            date_str = date_val.strftime("%Y-%m-%d")
        else:
            date_str = str(date_val)[:10]

        if value <= 0:
            continue
        records.append({"date": date_str, "value": value})

    print(f"  Parsed {len(records)} records from recent data")
    if records:
        print(f"  Range: {records[0]['date']} ~ {records[-1]['date']}")
    return records


def make_event_key(provider: str, country: str, event: str, datetime_raw: str) -> str:
    """イベントキーのハッシュ生成"""
    raw = f"{provider}|{country}|{event}|{datetime_raw}"
    return hashlib.sha256(raw.encode()).hexdigest()


def import_to_db(records: list, source_label: str) -> int:
    """レコードをDBに挿入（既存データは上書きしない）"""
    if not records:
        return 0

    inserted = 0
    skipped = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for rec in records:
                date_str = rec["date"]
                value = rec["value"]

                # datetime_utc: 金曜18:00 EST (23:00 UTC) とする
                datetime_raw = f"{date_str} 23:00:00"
                dt_utc = datetime.strptime(f"{date_str} 23:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)

                event_key = make_event_key(PROVIDER, COUNTRY, EVENT_NAME, datetime_raw)

                try:
                    cur.execute("""
                        INSERT INTO economic_calendar_events
                            (provider, event_key, country, event, datetime_utc, datetime_raw,
                             actual, unit, impact, currency, raw_json)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (provider, event_key) DO NOTHING
                    """, (
                        PROVIDER,
                        event_key,
                        COUNTRY,
                        EVENT_NAME,
                        dt_utc,
                        datetime_raw,
                        value,
                        "rigs",
                        IMPACT,
                        CURRENCY,
                        '{}',
                    ))

                    if cur.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1

                except Exception as e:
                    print(f"  Error inserting {date_str}: {e}")
                    conn.rollback()
                    continue

            conn.commit()

    print(f"  {source_label}: Inserted {inserted}, Skipped {skipped} (already exist)")
    return inserted


def main():
    print("=" * 60)
    print("Baker Hughes Oil Rig Count - Excel Import")
    print("=" * 60)

    total_inserted = 0

    # 1. Historical data (1987-2024) - XLSB format
    print("\n[1] Historical data (1987-2024)...")
    try:
        content = download_or_load(HISTORICAL_URL, LOCAL_FILE_HISTORICAL)
        records = parse_historical_xlsb(content)
        total_inserted += import_to_db(records, "historical")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("  Skipping historical data. Place the file at:")
        print(f"  {LOCAL_FILE_HISTORICAL}")

    # 2. Recent data (2024-2026) - XLSX format, NAM Weekly sheet
    print("\n[2] Recent data (2024-2026)...")
    recent_path = LOCAL_FILE_RECENT
    if not recent_path.exists():
        try:
            content = download_or_load(RECENT_URL, recent_path)
        except Exception as e:
            print(f"  Download failed: {e}")
            recent_path = None

    if recent_path and recent_path.exists():
        try:
            records = parse_recent_xlsx(recent_path)
            total_inserted += import_to_db(records, "recent")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("  Skipping recent data. Place the file at:")
        print(f"  {LOCAL_FILE_RECENT}")

    print(f"\n{'=' * 60}")
    print(f"Total inserted: {total_inserted}")
    print("=" * 60)

    # Verify
    print("\nVerifying...")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*), MIN(datetime_utc), MAX(datetime_utc)
                    FROM economic_calendar_events
                    WHERE event ILIKE %s
                """, (f"%{EVENT_NAME}%",))
                count, min_dt, max_dt = cur.fetchone()
                print(f"  Total records in DB: {count}")
                if min_dt:
                    print(f"  Range: {min_dt.strftime('%Y-%m-%d')} ~ {max_dt.strftime('%Y-%m-%d')}")

                # actual IS NOT NULL count
                cur.execute("""
                    SELECT COUNT(*)
                    FROM economic_calendar_events
                    WHERE event ILIKE %s AND actual IS NOT NULL
                """, (f"%{EVENT_NAME}%",))
                actual_count = cur.fetchone()[0]
                print(f"  Records with actual values: {actual_count}")
    except Exception as e:
        print(f"  Verify error: {e}")


if __name__ == "__main__":
    main()
