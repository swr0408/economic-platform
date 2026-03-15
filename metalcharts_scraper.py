#!/usr/bin/env python3
"""
MetalCharts Exchange Inventory Scraper v4
=========================================
Fetches warehouse inventory & settlement price data from MetalCharts.org
for SHFE (Shanghai) and COMEX exchanges via Playwright browser automation.

Data availability (as of 2026-03):
  COMEX Copper Inventory : 8,187 records (1993-04 ~ present, daily)
  SHFE  Copper Inventory :    79 records (2025-11 ~ present, weekly)
  SHFE  Settlement Prices: 5,556 records (2002-01 ~ present, daily)

Requirements:
  pip install playwright
  python -m playwright install chromium

Usage:
  python metalcharts_scraper.py                              # SHFE copper (default)
  python metalcharts_scraper.py --exchange comex             # COMEX copper (1993~)
  python metalcharts_scraper.py --exchange comex --metal HG  # COMEX copper
  python metalcharts_scraper.py --exchange shfe --metal cu,al,zn  # Multiple SHFE metals
  python metalcharts_scraper.py --exchange comex,shfe --metal cu  # Both exchanges
"""

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime

# ─── Metal mappings ──────────────────────────────────────────────────────────

SHFE_METALS = {
    "cu": "Copper", "al": "Aluminum", "zn": "Zinc", "pb": "Lead",
    "ni": "Nickel", "sn": "Tin", "au": "Gold", "ag": "Silver",
}
SHFE_PAGE = {
    "cu": "copper", "al": "aluminum", "zn": "zinc", "pb": "lead",
    "ni": "nickel", "sn": "tin", "au": "gold", "ag": "silver",
}

COMEX_METALS = {
    "HG": "Copper", "GC": "Gold", "SI": "Silver", "PL": "Platinum", "PA": "Palladium",
}
COMEX_PAGE = {
    "HG": "copper", "GC": "gold", "SI": "silver", "PL": "platinum", "PA": "palladium",
}


# ─── Scrape one exchange/metal combination ───────────────────────────────────

async def scrape_page(browser, exchange: str, metal_code: str) -> dict:
    """
    Load a MetalCharts page, click ALL, and capture API data.
    Returns dict of captured API responses.
    """
    if exchange == "shfe":
        page_name = SHFE_PAGE.get(metal_code.lower(), metal_code.lower())
        url = f"https://metalcharts.org/shfe/{page_name}"
        api_prefix = "/api/shfe/"
    elif exchange == "comex":
        page_name = COMEX_PAGE.get(metal_code.upper(), metal_code.lower())
        url = f"https://metalcharts.org/comex/{page_name}"
        api_prefix = "/api/comex/"
    else:
        return {}

    captured = {}

    page = await browser.new_page()

    async def on_response(response):
        rurl = response.url
        if api_prefix not in rurl:
            return
        if response.status != 200:
            return
        try:
            body = await response.text()
            data = json.loads(body)
            if data.get("success"):
                # Key by the path portion
                path = rurl.split("metalcharts.org")[1]
                captured[path] = data
        except Exception:
            pass

    page.on("response", on_response)

    print(f"    Loading {url} ...")
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"    Page load error: {e}")
        await page.close()
        return captured

    await page.wait_for_timeout(3000)

    # Click ALL button to get maximum data range
    try:
        buttons = await page.query_selector_all("button")
        for btn in buttons:
            text = (await btn.inner_text()).strip().upper()
            if text == "ALL":
                visible = await btn.is_visible()
                if visible:
                    await btn.click()
                    await page.wait_for_timeout(5000)
                    break
    except Exception:
        pass

    await page.wait_for_timeout(2000)
    await page.close()
    return captured


# ─── Build CSV rows from captured data ───────────────────────────────────────

def extract_inventory_rows(exchange: str, metal_code: str, metal_name: str,
                           captured: dict) -> list:
    """Extract inventory time series from captured API data."""
    rows = []

    # Find the inventory range=ALL response
    inv_data = None
    for path, data in captured.items():
        if "inventory" in path and "range=" in path:
            new_data = data.get("data", [])
            if inv_data is None or len(new_data) > len(inv_data):
                inv_data = new_data

    if inv_data:
        for item in inv_data:
            rows.append({
                "date": item.get("date", ""),
                "exchange": exchange.upper(),
                "commodity_code": metal_code.upper(),
                "commodity_name": metal_name,
                "data_type": "inventory",
                "value": item.get("total", item.get("warrant", "")),
                "unit": "tonnes",
            })

    return rows


def extract_settlement_rows(exchange: str, metal_code: str, metal_name: str,
                            captured: dict) -> list:
    """Extract settlement price time series from captured API data."""
    rows = []

    stl_data = None
    for path, data in captured.items():
        if "settlement" in path and "range=" in path:
            new_data = data.get("data", [])
            if stl_data is None or len(new_data) > len(stl_data):
                stl_data = new_data

    if stl_data:
        for item in stl_data:
            rows.append({
                "date": item.get("date", ""),
                "exchange": exchange.upper(),
                "commodity_code": metal_code.upper(),
                "commodity_name": metal_name,
                "data_type": "settlement_price",
                "value": item.get("total", ""),
                "unit": "CNY/tonne" if exchange == "shfe" else "USD",
            })

    return rows


def build_merged_rows(exchange: str, metal_code: str, metal_name: str,
                      captured: dict) -> list:
    """
    Build merged rows: one row per date with inventory and settlement columns.
    """
    # Collect inventory data (with registered/eligible for COMEX)
    inv_by_date = {}
    for path, data in captured.items():
        if "inventory" in path and "range=" in path:
            items = data.get("data", [])
            if not isinstance(items, list):
                continue
            for item in items:
                d = item.get("date", "")
                total = item.get("total", item.get("warrant", ""))
                if d and total != "":
                    inv_by_date[d] = {
                        "total": total,
                        "registered": item.get("registered", ""),
                        "eligible": item.get("eligible", ""),
                    }

    # Get unit from latest detail
    inv_unit = "tonnes"
    for path, data in captured.items():
        if "type=latest" in path and "inventory" in path:
            d = data.get("data", {})
            if isinstance(d, dict) and d.get("unit"):
                inv_unit = d["unit"]

    # Collect settlement data
    stl_by_date = {}
    for path, data in captured.items():
        if "settlement" in path and "range=" in path:
            items = data.get("data", [])
            if not isinstance(items, list):
                continue
            for item in items:
                d = item.get("date", "")
                v = item.get("total", "")
                if d and v != "":
                    stl_by_date[d] = v

    # Collect delivery notices (COMEX)
    dlv_by_date = {}
    for path, data in captured.items():
        if "delivery-notices" in path and "range=" in path:
            items = data.get("data", [])
            if not isinstance(items, list):
                continue
            for item in items:
                d = item.get("date", "")
                v = item.get("total", item.get("stopped", ""))
                if d and v != "":
                    dlv_by_date[d] = v

    # Latest detail
    latest_info = {}
    for path, data in captured.items():
        if "type=latest" in path and "inventory" in path:
            d = data.get("data", {})
            if isinstance(d, dict) and d.get("date"):
                latest_info = d

    # Merge all dates
    all_dates = sorted(set(
        list(inv_by_date.keys()) +
        list(stl_by_date.keys())
    ))

    price_unit = "CNY" if exchange == "shfe" else "USD"

    # Check if any record has registered/eligible
    has_reg_elig = any(
        inv.get("registered", "") not in ("", None)
        for inv in inv_by_date.values()
    )

    rows = []
    for date in all_dates:
        inv = inv_by_date.get(date, {})
        row = {
            "date": date,
            "exchange": exchange.upper(),
            "commodity_code": metal_code.upper(),
            "commodity_name": metal_name,
            "inventory_total": inv.get("total", "") if inv else "",
            "inventory_unit": inv_unit if inv else "",
        }
        if has_reg_elig:
            reg = inv.get("registered", "") if inv else ""
            elig = inv.get("eligible", "") if inv else ""
            row["inventory_registered"] = reg if reg is not None else ""
            row["inventory_eligible"] = elig if elig is not None else ""

        row[f"settlement_price_{price_unit.lower()}"] = stl_by_date.get(date, "")
        rows.append(row)

    return rows


# ─── Main ────────────────────────────────────────────────────────────────────

async def main_async(args):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("\n  Playwright not installed. Run:")
        print("    pip install playwright")
        print("    python -m playwright install chromium")
        sys.exit(1)

    exchanges = [e.strip().lower() for e in args.exchange.split(",")]
    metals_input = [m.strip() for m in args.metal.split(",")]

    tasks = []
    for exch in exchanges:
        for metal in metals_input:
            if exch == "shfe":
                code = metal.lower()
                if code not in SHFE_METALS:
                    print(f"  WARNING: Unknown SHFE metal '{code}', skipping.")
                    continue
                name = SHFE_METALS[code]
                tasks.append((exch, code, name))
            elif exch == "comex":
                code = metal.upper()
                if code not in COMEX_METALS:
                    # Try mapping lowercase
                    mapping = {"cu": "HG", "copper": "HG", "gold": "GC", "au": "GC",
                               "silver": "SI", "ag": "SI", "pt": "PL", "pd": "PA"}
                    code = mapping.get(metal.lower(), metal.upper())
                if code not in COMEX_METALS:
                    print(f"  WARNING: Unknown COMEX metal '{metal}', skipping.")
                    continue
                name = COMEX_METALS[code]
                tasks.append((exch, code, name))

    if not tasks:
        print("  No valid exchange/metal combinations.")
        sys.exit(1)

    label = "_".join(f"{e.upper()}_{c.upper()}" for e, c, _ in tasks)
    output_path = args.output or f"metalcharts_{label}_{datetime.now():%Y%m%d}.csv"

    print(f"\n{'=' * 65}")
    print(f"  MetalCharts Exchange Inventory Scraper v4")
    print(f"{'=' * 65}")
    print(f"  Tasks  : {', '.join(f'{e.upper()} {n} ({c.upper()})' for e, c, n in tasks)}")
    print(f"  Output : {output_path}")
    print(f"{'=' * 65}\n")

    all_rows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for exch, code, name in tasks:
            print(f"\n  === {exch.upper()} {name} ({code.upper()}) ===")

            captured = await scrape_page(browser, exch, code)
            print(f"    Captured {len(captured)} API responses:")
            for path, data in sorted(captured.items()):
                rng = data.get("range", "-")
                items = data.get("data", [])
                if isinstance(items, dict):
                    # Single record (e.g. type=latest, type=depositories)
                    print(f"           1 record  | {items.get('date', '?')} | {path}")
                    continue
                count = len(items)
                first = items[0].get("date", "?") if items else "?"
                last = items[-1].get("date", "?") if items else "?"
                print(f"      {count:>6} records | {first} ~ {last} | {path}")

            rows = build_merged_rows(exch, code, name, captured)
            all_rows.extend(rows)
            print(f"    CSV rows: {len(rows):,}")

        await browser.close()

    if not all_rows:
        print("\n  ERROR: No data captured. Check network connectivity.")
        sys.exit(1)

    # Determine fieldnames from data - ordered logically
    all_keys = set()
    for row in all_rows:
        all_keys.update(row.keys())

    # Preferred column order
    preferred = [
        "date", "exchange", "commodity_code", "commodity_name",
        "inventory_total", "inventory_registered", "inventory_eligible",
        "inventory_unit",
    ]
    fieldnames = [k for k in preferred if k in all_keys]
    for k in sorted(all_keys):
        if k not in fieldnames:
            fieldnames.append(k)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n{'=' * 65}")
    print(f"  Output: {output_path} ({len(all_rows):,} rows)")
    print(f"{'=' * 65}")

    for exch, code, name in tasks:
        task_rows = [r for r in all_rows
                     if r["exchange"] == exch.upper() and r["commodity_code"] == code.upper()]
        if not task_rows:
            continue
        dates = [r["date"] for r in task_rows]
        inv_count = sum(1 for r in task_rows if r.get("inventory_total", "") != "")
        reg_count = sum(1 for r in task_rows if r.get("inventory_registered", "") not in ("", None))
        stl_key = [k for k in task_rows[0].keys() if "settlement" in k]
        stl_count = sum(1 for r in task_rows if stl_key and r.get(stl_key[0], "") != "") if stl_key else 0
        print(f"  {exch.upper()} {name} ({code.upper()}): {dates[0]} ~ {dates[-1]}")
        print(f"    Inventory: {inv_count:,} records" +
              (f" (Registered/Eligible: {reg_count:,})" if reg_count else "") +
              f", Settlement: {stl_count:,} records")

    print(f"\n  Done! ✓\n")


def main():
    parser = argparse.ArgumentParser(
        description="MetalCharts Exchange Inventory Scraper (SHFE + COMEX)")
    parser.add_argument("--exchange", type=str, default="shfe",
                        help="Exchange(s): shfe, comex, or shfe,comex (default: shfe)")
    parser.add_argument("--metal", type=str, default="cu",
                        help="Metal code(s): cu,al,zn,pb,ni,sn,au,ag (SHFE) / "
                             "HG,GC,SI,PL,PA or cu,gold,silver (COMEX). Default: cu")
    parser.add_argument("--output", "-o", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
