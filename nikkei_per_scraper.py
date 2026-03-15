#!/usr/bin/env python3
"""
Nikkei 225 PER (Price Earnings Ratio) Historical Scraper
========================================================
Source: indexes.nikkei.co.jp
Method: Playwright form automation (month/year selector → table extract)
Data: Weekly PER values from 2005-01 onwards

Requirements:
  pip install playwright
  python -m playwright install chromium

Usage:
  python nikkei_per_scraper.py                        # Full history (2005-01 ~ now)
  python nikkei_per_scraper.py --from 2020-01         # From 2020-01
  python nikkei_per_scraper.py --list per             # PER (default)
  python nikkei_per_scraper.py --list pbr             # PBR
  python nikkei_per_scraper.py --list dy              # Dividend Yield
  python nikkei_per_scraper.py --list epr             # Earnings Per Share
"""

import argparse
import asyncio
import csv
import re
import sys
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Required:")
    print("  pip install playwright")
    print("  python -m playwright install chromium")
    sys.exit(1)

LIST_TYPES = {
    "per": "PER (Price Earnings Ratio)",
    "pbr": "PBR (Price Book Ratio)",
    "dy":  "Dividend Yield",
    "epr": "Earnings Per Share",
}

BASE_URL = "https://indexes.nikkei.co.jp/en/nkave/archives/data?list={list_type}"


def parse_date(date_text: str) -> str:
    """Parse 'Mar/02/2026' or similar to 'YYYY-MM-DD'."""
    date_text = date_text.strip()
    for fmt in ("%b/%d/%Y", "%b %d,%Y", "%b %d, %Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_text


async def scrape_nikkei_per(args):
    list_type = args.list.lower()
    list_label = LIST_TYPES.get(list_type, list_type.upper())

    # Parse date range
    now = datetime.now()
    end_year, end_month = now.year, now.month

    if args.from_date:
        parts = args.from_date.split("-")
        start_year, start_month = int(parts[0]), int(parts[1])
    else:
        start_year, start_month = 2005, 1

    output = args.output or f"nikkei225_{list_type}_{start_year}{start_month:02d}_{end_year}{end_month:02d}.csv"

    print(f"\n{'=' * 60}")
    print(f"  Nikkei 225 {list_label} Historical Scraper")
    print(f"{'=' * 60}")
    print(f"  Period : {start_year}-{start_month:02d} ~ {end_year}-{end_month:02d}")
    print(f"  Output : {output}")
    print(f"{'=' * 60}\n")

    # Build list of (year, month) to scrape
    months_to_scrape = []
    y, m = start_year, start_month
    while (y < end_year) or (y == end_year and m <= end_month):
        months_to_scrape.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    print(f"  Months to scrape: {len(months_to_scrape)}")

    all_rows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        page = await context.new_page()

        # Load initial page
        print(f"  Loading initial page...")
        url = BASE_URL.format(list_type=list_type)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        for idx, (year, month) in enumerate(months_to_scrape):
            progress = f"[{idx+1}/{len(months_to_scrape)}]"

            try:
                # Select year and month from dropdowns
                selects = await page.query_selector_all("select")
                if len(selects) < 2:
                    print(f"  {progress} {year}-{month:02d} - no selects found, reloading...")
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    selects = await page.query_selector_all("select")

                if len(selects) >= 2:
                    month_select = selects[0]
                    year_select = selects[1]

                    await month_select.select_option(value=str(month))
                    await year_select.select_option(value=str(year))

                    # Click the submit/display button
                    btn = await page.query_selector('input[type="submit"], button[type="submit"]')
                    if btn:
                        await btn.click()
                    else:
                        # Try finding any button near the form
                        display_btn = await page.query_selector('input.btn, button.btn, input[value*="Display"], input[value*="display"], input[value*="Go"]')
                        if display_btn:
                            await display_btn.click()
                        else:
                            # Try pressing Enter on the last select
                            await year_select.press("Enter")

                    await page.wait_for_timeout(2000)

                # Extract table data
                table = await page.query_selector("table")
                if not table:
                    print(f"  {progress} {year}-{month:02d} - no table")
                    continue

                trs = await table.query_selector_all("tr")
                month_rows = []

                for tr in trs[1:]:  # Skip header
                    tds = await tr.query_selector_all("td")
                    if len(tds) >= 3:
                        date_text = (await tds[0].inner_text()).strip()
                        val1 = (await tds[1].inner_text()).strip()
                        val2 = (await tds[2].inner_text()).strip()

                        if not date_text or date_text.lower() == "date":
                            continue

                        parsed_date = parse_date(date_text)

                        def clean_num(s):
                            s = s.strip().replace(",", "")
                            if s in ("", "-", "N/A", "--"):
                                return ""
                            try:
                                return float(s)
                            except ValueError:
                                return ""

                        row = {
                            "date": parsed_date,
                            "market_cap_basis": clean_num(val1),
                            "index_weight_basis": clean_num(val2),
                        }
                        month_rows.append(row)

                all_rows.extend(month_rows)

                if month_rows:
                    if idx <= 2 or (idx + 1) % 20 == 0:
                        print(f"  {progress} {year}-{month:02d} ✓ {len(month_rows)} rows "
                              f"({month_rows[0]['date']} ~ {month_rows[-1]['date']})")
                else:
                    if idx <= 5:
                        print(f"  {progress} {year}-{month:02d} - 0 rows")

            except Exception as e:
                print(f"  {progress} {year}-{month:02d} - error: {str(e)[:80]}")
                # Try reloading
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(2000)
                except:
                    pass

            await page.wait_for_timeout(500)

        await browser.close()

    if not all_rows:
        print("\n  ERROR: No data collected.")
        sys.exit(1)

    # Remove duplicates and sort
    seen = set()
    unique_rows = []
    for r in all_rows:
        if r["date"] not in seen:
            seen.add(r["date"])
            unique_rows.append(r)
    unique_rows.sort(key=lambda x: x["date"])

    # Write CSV
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "market_cap_basis", "index_weight_basis"])
        writer.writeheader()
        writer.writerows(unique_rows)

    print(f"\n{'=' * 60}")
    print(f"  Output: {output} ({len(unique_rows):,} rows)")
    print(f"  Period: {unique_rows[0]['date']} ~ {unique_rows[-1]['date']}")

    vals = [r["market_cap_basis"] for r in unique_rows if r["market_cap_basis"] != ""]
    if vals:
        print(f"  {list_label} (Market Cap): {min(vals):.2f} ~ {max(vals):.2f}")

    print(f"\n  Done! ✓\n")


def main():
    parser = argparse.ArgumentParser(description="Nikkei 225 PER/PBR Historical Scraper")
    parser.add_argument("--list", type=str, default="per",
                        help="Data type: per, pbr, dy, epr (default: per)")
    parser.add_argument("--from", dest="from_date", type=str, default=None,
                        help="Start YYYY-MM (default: 2005-01)")
    parser.add_argument("--output", "-o", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(scrape_nikkei_per(args))


if __name__ == "__main__":
    main()
