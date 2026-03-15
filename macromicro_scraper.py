#!/usr/bin/env python3
"""
MacroMicro Series Data Scraper
===============================
Extracts chart data from any MacroMicro series page via Highcharts JS extraction.
Requires headed browser (Cloudflare bot detection bypass).

Requirements:
  pip install playwright
  python -m playwright install chromium

Usage:
  python macromicro_scraper.py https://en.macromicro.me/series/23955/nasdaq-100-pe
  python macromicro_scraper.py https://en.macromicro.me/series/8743/copper-shfe-warehouse-stock
  python macromicro_scraper.py https://en.macromicro.me/series/3613/copper-lme-warehouse-stock
  python macromicro_scraper.py URL1 URL2 URL3   # Multiple series at once
  python macromicro_scraper.py URL -o output.csv
"""

import argparse
import asyncio
import csv
import json
import re
import sys
from datetime import datetime, timezone

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Required:")
    print("  pip install playwright")
    print("  python -m playwright install chromium")
    sys.exit(1)


def ts_to_date(ts_ms: int) -> str:
    """Convert millisecond Unix timestamp to YYYY-MM-DD."""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def slug_from_url(url: str) -> str:
    """Extract slug from MacroMicro URL for filename."""
    m = re.search(r'/series/\d+/([^/?#]+)', url)
    return m.group(1) if m else "unknown"


async def scrape_series(context, url: str, wait_seconds: int = 20) -> list:
    """
    Load a MacroMicro series page and extract Highcharts data.
    Returns list of dicts with series name, date, value.
    """
    page = await context.new_page()

    print(f"  Loading {url} ...")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"  Load error (continuing): {e}")

    print(f"  Waiting {wait_seconds}s for chart render...")
    await page.wait_for_timeout(wait_seconds * 1000)

    # Extract all Highcharts series data
    result = await page.evaluate("""() => {
        if (!window.Highcharts) return { error: "No Highcharts found" };
        const charts = Highcharts.charts.filter(c => c);
        if (charts.length === 0) return { error: "No charts found" };
        
        const out = [];
        for (const chart of charts) {
            for (const s of chart.series) {
                out.push({
                    name: s.name || "Unknown",
                    data: s.data.map(d => [d.x, d.y])
                });
            }
        }
        return { series: out };
    }""")

    await page.close()

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return []

    rows = []
    for s in result.get("series", []):
        name = s["name"]
        points = s["data"]
        print(f"  Series: {name} ({len(points)} points)")
        if points:
            print(f"    {ts_to_date(points[0][0])} ~ {ts_to_date(points[-1][0])}")

        for ts_ms, value in points:
            if value is not None:
                rows.append({
                    "date": ts_to_date(ts_ms),
                    "series_name": name,
                    "value": value,
                })

    return rows


async def main_async(args):
    urls = args.urls
    wait = args.wait

    print(f"\n{'=' * 65}")
    print(f"  MacroMicro Series Scraper")
    print(f"{'=' * 65}")
    print(f"  URLs  : {len(urls)}")
    print(f"  Wait  : {wait}s per page")
    print(f"{'=' * 65}\n")

    all_rows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            delete navigator.__proto__.webdriver;
        """)

        for i, url in enumerate(urls):
            print(f"\n  [{i+1}/{len(urls)}] {url}")
            rows = await scrape_series(context, url, wait)
            # Tag with source URL
            for r in rows:
                r["source_url"] = url
                r["source_slug"] = slug_from_url(url)
            all_rows.extend(rows)

        await browser.close()

    if not all_rows:
        print("\n  ERROR: No data extracted.")
        print("  If Cloudflare blocked the page, try increasing --wait")
        sys.exit(1)

    # Output filename
    if args.output:
        output_path = args.output
    elif len(urls) == 1:
        slug = slug_from_url(urls[0])
        output_path = f"macromicro_{slug}.csv"
    else:
        output_path = f"macromicro_{datetime.now():%Y%m%d_%H%M%S}.csv"

    # Write CSV
    fieldnames = ["date", "series_name", "value", "source_slug", "source_url"]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n{'=' * 65}")
    print(f"  Output: {output_path} ({len(all_rows):,} rows)")
    print(f"{'=' * 65}")

    # Summary
    series_names = set(r["series_name"] for r in all_rows)
    for name in sorted(series_names):
        s_rows = [r for r in all_rows if r["series_name"] == name]
        dates = [r["date"] for r in s_rows]
        vals = [r["value"] for r in s_rows]
        print(f"  {name}")
        print(f"    {len(s_rows)} points | {dates[0]} ~ {dates[-1]} | "
              f"{min(vals):.2f} ~ {max(vals):.2f}")

    print(f"\n  Done! ✓\n")


def main():
    parser = argparse.ArgumentParser(description="MacroMicro Series Scraper")
    parser.add_argument("urls", nargs="+", help="MacroMicro series URL(s)")
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--wait", type=int, default=20,
                        help="Seconds to wait for chart render (default: 20)")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
