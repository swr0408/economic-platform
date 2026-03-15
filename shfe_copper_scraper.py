#!/usr/bin/env python3
"""
SHFE Copper Warehouse Stock Scraper (commoditieschart.net)
==========================================================
Data is embedded in page HTML as JSON - no API auth needed.
~4,200 daily records from 2008-10-06 to present.

Requirements: pip install requests
Usage:
  python shfe_copper_scraper.py
  python shfe_copper_scraper.py --slug shfe-zinc-stocks
  python shfe_copper_scraper.py --slug shfe-gold-stocks
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("Required: pip install requests")
    sys.exit(1)

# Available SHFE slugs on commoditieschart.net
AVAILABLE = {
    "shfe-copper-stocks":  ("copper", "CU", "Copper"),
    "shfe-zinc-stocks":    ("zinc",   "ZN", "Zinc"),
    "shfe-nickel-stocks":  ("nickel", "NI", "Nickel"),
    "shfe-gold-stocks":    ("gold",   "AU", "Gold"),
    "shfe-aluminum-stocks": ("aluminum", "AL", "Aluminum"),
    "shfe-lead-stocks":    ("lead",   "PB", "Lead"),
    "shfe-tin-stocks":     ("tin",    "SN", "Tin"),
}


def fetch_and_parse(slug: str) -> list:
    info = AVAILABLE.get(slug)
    if not info:
        print(f"Unknown slug: {slug}")
        print(f"Available: {', '.join(AVAILABLE.keys())}")
        sys.exit(1)

    metal_page, code, name = info
    url = f"https://commoditieschart.net/metals/{metal_page}/{slug}"

    print(f"  Fetching {url} ...")
    r = requests.get(url, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    if r.status_code != 200:
        print(f"  HTTP {r.status_code} - failed")
        sys.exit(1)

    print(f"  Page: {len(r.text):,} chars")

    # Data is inside self.__next_f.push() with escaped quotes: \"d\":\"2008-12-01\"
    # Pattern 1: {"d":"YYYY-MM-DD","v":12345,...}  (with escaped quotes)
    pattern = r'\{\\"d\\":\\"(\d{4}-\d{2}-\d{2})\\",\\"v\\":(\d+)'
    matches = re.findall(pattern, r.text)
    print(f"  Pattern 1 matches: {len(matches)}")

    rows = []
    seen = set()
    for date_str, value in matches:
        if date_str not in seen:
            seen.add(date_str)
            rows.append({
                "date": date_str,
                "commodity_code": code,
                "commodity_name": name,
                "warehouse_stock_tonnes": int(value),
            })

    # Pattern 2: ["MMM DD,YYYY",value]  (with escaped quotes)
    pattern2 = r'\[\\"([A-Z][a-z]{2} \d{2},\d{4})\\",(\d+)\]'
    matches2 = re.findall(pattern2, r.text)
    print(f"  Pattern 2 matches: {len(matches2)}")
    for date_raw, value in matches2:
        try:
            dt = datetime.strptime(date_raw, "%b %d,%Y")
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in seen:
                seen.add(date_str)
                rows.append({
                    "date": date_str,
                    "commodity_code": code,
                    "commodity_name": name,
                    "warehouse_stock_tonnes": int(value),
                })
        except ValueError:
            continue

    rows.sort(key=lambda x: x["date"])
    return rows


def main():
    parser = argparse.ArgumentParser(description="SHFE Warehouse Stock Scraper")
    parser.add_argument("--slug", type=str, default="shfe-copper-stocks",
                        help="Page slug (default: shfe-copper-stocks)")
    parser.add_argument("--output", "-o", type=str, default=None)
    args = parser.parse_args()

    info = AVAILABLE.get(args.slug, ("", args.slug.upper(), ""))
    _, code, name = info

    print(f"\n{'=' * 60}")
    print(f"  SHFE Warehouse Stock Scraper (commoditieschart.net)")
    print(f"{'=' * 60}")
    print(f"  Metal: {name} ({code})")
    print(f"{'=' * 60}\n")

    rows = fetch_and_parse(args.slug)

    if not rows:
        print("  ERROR: No data extracted.")
        sys.exit(1)

    output = args.output or f"shfe_{code.lower()}_warehouse_stocks.csv"

    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[
            "date", "commodity_code", "commodity_name", "warehouse_stock_tonnes"])
        w.writeheader()
        w.writerows(rows)

    vals = [r["warehouse_stock_tonnes"] for r in rows]
    print(f"  Records : {len(rows):,}")
    print(f"  Period  : {rows[0]['date']} ~ {rows[-1]['date']}")
    print(f"  Range   : {min(vals):,} ~ {max(vals):,} tonnes")
    print(f"  Output  : {output}")
    print(f"\n  Done! ✓\n")


if __name__ == "__main__":
    main()
