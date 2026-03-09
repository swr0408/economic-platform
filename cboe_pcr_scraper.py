#!/usr/bin/env python3
"""
CBOE Put/Call Ratio スクレイパー (Playwright版)
=============================================
2019-10-07 以降の CBOE Daily Market Statistics から
Total / Index / Equity / ETP の P/C Ratio を Playwright で取得して CSV 保存。

使い方:
  pip install playwright pandas
  playwright install chromium
  python cboe_pcr_scraper.py

  # 途中で止めても --resume で続きから再開
  python cboe_pcr_scraper.py --resume

  # totalpc.csv と同じフォルダに置くと自動マージ
"""

import argparse
import asyncio
import csv
import os
import re
import sys
from datetime import date, datetime, timedelta

import pandas as pd
from playwright.async_api import async_playwright

# ── 設定 ─────────────────────────────────────────
START_DATE = date(2019, 10, 7)
END_DATE = date.today()
OUTPUT_CSV = "cboe_pcr_2019_to_present.csv"
MERGED_CSV = "cboe_pcr_full.csv"
ORIGINAL_CSV = "totalpc.csv"

FIELDNAMES = [
    "date",
    "total_pcr",
    "index_pcr",
    "etp_pcr",
    "equity_pcr",
    "vix_pcr",
    "spx_pcr",
]

# ページテキストの実際の形式:
#   TOTAL PUT/CALL RATIO\t0.90
#   INDEX PUT/CALL RATIO\t1.23
#   EXCHANGE TRADED PRODUCTS PUT/CALL RATIO\t0.94
#   EQUITY PUT/CALL RATIO\t0.57
PCR_PATTERNS = [
    ("total_pcr",  r"TOTAL\s+PUT/CALL\s+RATIO\s+([\d.]+)"),
    ("index_pcr",  r"INDEX\s+PUT/CALL\s+RATIO\s+([\d.]+)"),
    ("etp_pcr",    r"EXCHANGE\s+TRADED\s+PRODUCTS?\s+PUT/CALL\s+RATIO\s+([\d.]+)"),
    ("equity_pcr", r"EQUITY\s+PUT/CALL\s+RATIO\s+([\d.]+)"),
    ("vix_pcr",    r"VIX\)?\s+PUT/CALL\s+RATIO\s+([\d.]+)"),
    ("spx_pcr",    r"SPX\s*\+?\s*SPXW?\s+PUT/CALL\s+RATIO\s+([\d.]+)"),
]


def business_days(start, end):
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            yield cur
        cur += timedelta(days=1)


def load_existing(path):
    done = set()
    rows = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                done.add(r["date"])
                rows.append(r)
    return done, rows


def save_results(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: datetime.strptime(x["date"], "%m/%d/%Y")):
            w.writerow({k: r.get(k, "") for k in FIELDNAMES})


def merge_with_original(new_rows):
    if not os.path.exists(ORIGINAL_CSV):
        print(f"  {ORIGINAL_CSV} not found. Skipping merge.")
        return

    orig = pd.read_csv(
        ORIGINAL_CSV,
        skiprows=2,
        names=["DATE", "CALLS", "PUTS", "TOTAL", "P/C Ratio"],
        skipinitialspace=True,
    )
    orig = orig[orig["DATE"].str.match(r"^\d", na=False)].copy()
    orig["DATE"] = pd.to_datetime(orig["DATE"], format="mixed")
    orig["P/C Ratio"] = pd.to_numeric(orig["P/C Ratio"], errors="coerce")

    new = pd.DataFrame(new_rows)
    new["DATE"] = pd.to_datetime(new["date"], format="%m/%d/%Y")
    new = new.rename(columns={"total_pcr": "P/C Ratio"})
    new["P/C Ratio"] = pd.to_numeric(new["P/C Ratio"], errors="coerce")
    for c in ["CALLS", "PUTS", "TOTAL"]:
        if c not in new.columns:
            new[c] = ""

    merged = pd.concat(
        [
            orig[["DATE", "CALLS", "PUTS", "TOTAL", "P/C Ratio"]],
            new[["DATE", "CALLS", "PUTS", "TOTAL", "P/C Ratio"]],
        ],
        ignore_index=True,
    )
    merged = merged.drop_duplicates(subset=["DATE"], keep="last")
    merged = merged.sort_values("DATE").reset_index(drop=True)
    merged["DATE"] = merged["DATE"].dt.strftime("%m/%d/%Y")
    merged.to_csv(MERGED_CSV, index=False)
    print(f"  Merged -> {MERGED_CSV} ({len(merged)} total rows)")


async def scrape(args):
    dates = list(business_days(args.start, args.end))

    # --resume: 既存結果を引き継ぐ
    done_set, existing_rows = load_existing(OUTPUT_CSV)
    if args.resume and existing_rows:
        print(f"  Resuming: {len(done_set)} dates already done")

    remaining = [d for d in dates if f"{d:%m/%d/%Y}" not in done_set]
    if not remaining:
        print("  All dates already collected!")
        return existing_rows

    print(f"  Remaining: {len(remaining)} / {len(dates)} dates")
    print(f"  Estimated time: ~{len(remaining) * (args.sleep + 4) / 60:.0f} min")
    print()

    results = list(existing_rows)
    consecutive_fails = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for i, dt in enumerate(remaining, 1):
            url = (
                "https://www.cboe.com/us/options/market_statistics/daily/"
                f"?dt={dt:%Y-%m-%d}"
            )
            print(f"  [{i}/{len(remaining)}] {dt}...", end=" ", flush=True)

            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
                await page.wait_for_timeout(3000)
                text = await page.inner_text("body")

                row = {"date": f"{dt:%m/%d/%Y}"}
                found = False
                for key, pattern in PCR_PATTERNS:
                    m = re.search(pattern, text, re.IGNORECASE)
                    if m:
                        row[key] = m.group(1)
                        found = True

                if found:
                    results.append(row)
                    consecutive_fails = 0
                    print(f"OK  total={row.get('total_pcr', '?')}")
                else:
                    consecutive_fails += 1
                    print("no data (holiday?)")

            except Exception as e:
                consecutive_fails += 1
                print(f"error: {str(e)[:80]}")

            # 50件ごとに中間保存
            if i % 50 == 0:
                save_results(results, OUTPUT_CSV)
                print(f"    [saved: {len(results)} rows]")

            # 連続10回失敗で30秒待機
            if consecutive_fails >= 10:
                print("\n  10 consecutive failures. Pausing 30s...")
                await asyncio.sleep(30)
                consecutive_fails = 0

            await asyncio.sleep(args.sleep)

        await browser.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="CBOE P/C Ratio Scraper")
    parser.add_argument(
        "--start",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=START_DATE,
    )
    parser.add_argument(
        "--end",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=END_DATE,
    )
    parser.add_argument("--sleep", type=float, default=2.0, help="seconds between requests")
    parser.add_argument("--resume", action="store_true", help="resume from last run")
    parser.add_argument("--merge-only", action="store_true", help="merge only")
    args = parser.parse_args()

    print("=" * 60)
    print("CBOE P/C Ratio Scraper (Playwright)")
    print(f"Period : {args.start} -> {args.end}")
    print(f"Sleep  : {args.sleep}s")
    print("=" * 60)

    if args.merge_only:
        if os.path.exists(OUTPUT_CSV):
            _, rows = load_existing(OUTPUT_CSV)
            merge_with_original(rows)
        else:
            print(f"  {OUTPUT_CSV} not found.")
        return

    results = asyncio.run(scrape(args))

    if results:
        save_results(results, OUTPUT_CSV)
        print(f"\n  Saved {len(results)} rows -> {OUTPUT_CSV}")
        merge_with_original(results)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
