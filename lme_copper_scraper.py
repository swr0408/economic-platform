#!/usr/bin/env python3
"""
LME Copper Warehouse Stock Historical Data Scraper
Source: westmetall.com (2008-present)
Output: CSV with Date, Cash Settlement, 3-Month, Stock (tonnes)

Usage:
  pip install requests beautifulsoup4
  python lme_copper_scraper.py
"""

import csv
import re
import sys
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Required packages: pip install requests beautifulsoup4")
    sys.exit(1)


def fetch_and_parse():
    url = "https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Cu_cash"
    
    print(f"Fetching data from {url} ...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    rows = []
    
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) != 4:
                continue
            
            date_text = tds[0].get_text(strip=True)
            cash_text = tds[1].get_text(strip=True).replace(",", "")
            three_text = tds[2].get_text(strip=True).replace(",", "")
            stock_text = tds[3].get_text(strip=True).replace(",", "")
            
            # Skip header-like rows
            if "date" in date_text.lower() or "LME" in cash_text:
                continue
            
            # Skip missing data
            if cash_text == "-" or stock_text == "-" or not cash_text:
                continue
            
            try:
                dt = datetime.strptime(date_text, "%d. %B %Y")
                cash = float(cash_text)
                three = float(three_text)
                stock = int(float(stock_text))
                rows.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "cash": cash,
                    "three_month": three,
                    "stock": stock
                })
            except (ValueError, TypeError):
                continue
    
    # Sort ascending by date
    rows.sort(key=lambda x: x["date"])
    return rows


def write_csv(rows, output_path="lme_copper_warehouse_stocks_full.csv"):
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Date",
            "LME_Copper_Cash_Settlement_USD",
            "LME_Copper_3Month_USD",
            "LME_Copper_Stock_Tonnes"
        ])
        for row in rows:
            writer.writerow([row["date"], row["cash"], row["three_month"], row["stock"]])
    return output_path


def main():
    rows = fetch_and_parse()
    
    if not rows:
        print("ERROR: No data parsed. Check network connection.")
        sys.exit(1)
    
    output = write_csv(rows)
    
    print(f"\n=== LME Copper Warehouse Stock Data ===")
    print(f"Output: {output}")
    print(f"Total rows: {len(rows):,}")
    print(f"Date range: {rows[0]['date']} ~ {rows[-1]['date']}")
    print(f"Stock range: {min(r['stock'] for r in rows):,} ~ {max(r['stock'] for r in rows):,} tonnes")
    
    # Yearly summary
    from collections import Counter
    year_counts = Counter(r["date"][:4] for r in rows)
    print(f"\nYearly breakdown:")
    for year in sorted(year_counts.keys()):
        year_rows = [r for r in rows if r["date"].startswith(year)]
        min_s = min(r["stock"] for r in year_rows)
        max_s = max(r["stock"] for r in year_rows)
        print(f"  {year}: {year_counts[year]:>3} days | Stock: {min_s:>7,} ~ {max_s:>7,} tonnes")


if __name__ == "__main__":
    main()
