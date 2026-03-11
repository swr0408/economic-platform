"""
SSE 518880 (華安黄金ETF) 基金规模 日次データ スクレイピング

上海証券交易所の裏APIから総份額（万份）の日次時系列データを取得し、CSVを生成する。

API: http://query.sse.com.cn/commonQuery.do
sqlId: COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_SEARCH_L

Usage:
    python backend/scripts/scrape_sse_fund_scale.py
"""

import csv
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

# --- Config ---
FUND_CODE = "518880"
START_DATE = date(2019, 3, 1)
END_DATE = date.today()
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "market"
OUTPUT_FILE = OUTPUT_DIR / "sse_518880_fund_scale_cache.csv"

API_URL = "http://query.sse.com.cn/commonQuery.do"
SQL_ID = "COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_SEARCH_L"
HEADERS = {
    "Host": "query.sse.com.cn",
    "Referer": "http://www.sse.com.cn/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Rate limiting: pause between requests (seconds)
REQUEST_DELAY = 0.15
# Batch size for progress reporting
BATCH_LOG_SIZE = 100

JSONP_RE = re.compile(r"cb\((.*)\)", re.DOTALL)


def fetch_one(session: requests.Session, query_date: str) -> dict | None:
    """Fetch fund scale for a single date. Returns result dict or None."""
    params = {
        "jsonCallBack": "cb",
        "isPagination": "false",
        "sqlId": SQL_ID,
        "SEC_CODE": FUND_CODE,
        "STAT_DATE": query_date,
    }
    try:
        r = session.get(API_URL, params=params, headers=HEADERS, timeout=10)
        m = JSONP_RE.search(r.text)
        if not m:
            return None
        data = json.loads(m.group(1))
        result = data.get("result")
        if result and len(result) > 0:
            return result[0]
    except Exception:
        pass
    return None


def generate_dates(start: date, end: date):
    """Generate all dates from start to end (inclusive), skipping weekends."""
    d = start
    while d <= end:
        # Skip Saturday (5) and Sunday (6)
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def load_existing(filepath: Path) -> dict:
    """Load existing CSV data into a dict keyed by date string."""
    existing = {}
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["date"]] = row
    return existing


def main():
    # Load existing data for incremental updates
    existing = load_existing(OUTPUT_FILE)
    if existing:
        print(f"Existing CSV: {len(existing)} records loaded")
        # Only fetch dates not already in CSV
        latest_existing = max(existing.keys())
        print(f"  Latest existing date: {latest_existing}")

    weekdays = list(generate_dates(START_DATE, END_DATE))
    to_fetch = [d for d in weekdays if d.isoformat() not in existing]

    if not to_fetch:
        print("All dates already fetched. CSV is up to date.")
        return

    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"Weekdays to fetch: {len(to_fetch)} (skipping {len(weekdays) - len(to_fetch)} already cached)")
    print(f"Output: {OUTPUT_FILE}")
    print()

    records = []
    session = requests.Session()
    fetched = 0
    errors = 0

    for i, d in enumerate(to_fetch):
        date_str = d.isoformat()
        result = fetch_one(session, date_str)

        if result:
            records.append({
                "date": result["STAT_DATE"],
                "fund_code": result["SEC_CODE"],
                "fund_name": result.get("FUND_EXPANSION_ABBR", ""),
                "total_shares_wan": result["TOT_VOL"],
            })
            fetched += 1
        else:
            # Non-trading day (holiday etc.) - skip silently
            errors += 1

        if (i + 1) % BATCH_LOG_SIZE == 0:
            pct = (i + 1) / len(to_fetch) * 100
            print(f"  [{pct:5.1f}%] {i + 1}/{len(to_fetch)} | fetched={fetched} | skipped={errors} | last={date_str}")

        time.sleep(REQUEST_DELAY)

    print(f"\nFetch complete: {fetched} records, {errors} non-trading days skipped")

    # Merge with existing data
    for rec in records:
        existing[rec["date"]] = rec

    # Sort by date and write CSV
    all_records = sorted(existing.values(), key=lambda x: x["date"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "fund_code", "fund_name", "total_shares_wan"])
        writer.writeheader()
        writer.writerows(all_records)

    print(f"CSV saved: {OUTPUT_FILE}")
    print(f"Total records: {len(all_records)}")
    if all_records:
        print(f"Date range: {all_records[0]['date']} ~ {all_records[-1]['date']}")


if __name__ == "__main__":
    main()
