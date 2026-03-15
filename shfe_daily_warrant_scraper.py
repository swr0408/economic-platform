#!/usr/bin/env python3
"""
SHFE Daily Warrant (Warehouse Stock) Historical Data Scraper  v3
================================================================
Source: Shanghai Futures Exchange (上海期货交易所)

Two modes:
  Mode 1 (default): Uses akshare library - most reliable, handles API changes
  Mode 2 (--direct): Direct SHFE API access with browser-like session

Usage:
  pip install akshare requests pandas
  python shfe_daily_warrant_scraper.py                          # Copper, last 1 year
  python shfe_daily_warrant_scraper.py --from 2020-01-01        # Copper from 2020
  python shfe_daily_warrant_scraper.py --metal CU,AL,ZN         # Multiple metals
  python shfe_daily_warrant_scraper.py --all --from 2023-01-01  # All commodities
  python shfe_daily_warrant_scraper.py --direct --from 2024-01-01  # Direct API mode
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict

# ─── Metal mappings ──────────────────────────────────────────────────────────

METAL_CN_TO_CODE = {
    "铜": "CU", "铝": "AL", "锌": "ZN", "铅": "PB",
    "镍": "NI", "锡": "SN", "黄金": "AU", "白银": "AG",
    "螺纹钢": "RB", "线材": "WR", "热轧卷板": "HC",
    "不锈钢": "SS", "氧化铝": "AO", "国际铜": "BC",
    "原油": "SC", "燃料油": "FU", "石油沥青": "BU",
    "天然橡胶": "RU", "20号胶": "NR", "纸浆": "SP",
    "低硫燃料油": "LU", "合成橡胶": "BR", "铝合金": "AD",
}

METAL_LABELS = {
    "CU": "Copper", "AL": "Aluminum", "ZN": "Zinc", "PB": "Lead",
    "NI": "Nickel", "SN": "Tin", "AU": "Gold", "AG": "Silver",
    "RB": "Steel Rebar", "WR": "Steel Wire Rod", "HC": "Hot Rolled Coils",
    "SS": "Stainless Steel", "AO": "Aluminium Oxide", "BC": "Bonded Copper",
    "SC": "Crude Oil", "FU": "Fuel Oil", "BU": "Bitumen",
    "RU": "Natural Rubber", "NR": "TSR 20", "SP": "Woodpulp",
    "LU": "LSFO", "BR": "Synthetic Rubber",
}


def cn_to_code(name: str) -> str:
    name = name.strip()
    for cn, code in METAL_CN_TO_CODE.items():
        if cn in name:
            return code
    m = re.search(r'\b([A-Z]{2})\b', name)
    return m.group(1) if m else ""


def safe_int(val) -> int:
    if val is None or val == "" or val == "-":
        return 0
    try:
        return int(float(str(val).replace(",", "").strip()))
    except (ValueError, TypeError):
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# MODE 1: akshare (recommended)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_via_akshare(start_date: datetime, end_date: datetime,
                      metals_filter: set | None, delay: float) -> list:
    """
    Use akshare's futures_shfe_warehouse_receipt to fetch data day by day.
    This handles SHFE API URL changes, session management, etc.
    """
    try:
        import akshare as ak
        import pandas as pd
    except ImportError:
        print("\n  akshare not installed. Install with:")
        print("    pip install akshare pandas")
        print("\n  Or use --direct mode for direct API access.")
        sys.exit(1)

    trading_days = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:
            trading_days.append(d)
        d += timedelta(days=1)

    print(f"\n  Weekdays to check: {len(trading_days)}")
    print(f"  Using akshare futures_shfe_warehouse_receipt()\n")

    all_rows = []
    ok = skip = err = 0

    for i, day in enumerate(trading_days):
        date_str = day.strftime("%Y%m%d")
        progress = f"[{i+1}/{len(trading_days)}]"

        try:
            result = ak.futures_shfe_warehouse_receipt(date=date_str)
        except Exception as e:
            err_msg = str(e)
            if "holiday" in err_msg.lower() or "not" in err_msg.lower() or "无" in err_msg:
                skip += 1
                if skip % 100 == 0:
                    print(f"  {progress} {day:%Y-%m-%d} - no data ({skip} skipped)")
                time.sleep(0.05)
                continue
            else:
                err += 1
                if err <= 5:
                    print(f"  {progress} {day:%Y-%m-%d} - error: {err_msg[:80]}")
                time.sleep(delay)
                continue

        if result is None or (isinstance(result, dict) and not result):
            skip += 1
            time.sleep(0.05)
            continue

        # akshare returns a dict of {commodity_name: DataFrame}
        # Each DF has columns: VARNAME, VARSORT, REGNAME, REGSORT, WRTQTY, WRTWGHTS, WRTCHANGE, etc.
        day_str = day.strftime("%Y-%m-%d")

        if isinstance(result, dict):
            for var_name, df in result.items():
                if df is None or df.empty:
                    continue

                code = cn_to_code(var_name)
                if not code:
                    continue
                if metals_filter and code not in metals_filter:
                    continue

                # Find the grand total row (ROWSTATUS=2 or last row with large ROWORDER)
                total_row = None
                if "ROWSTATUS" in df.columns:
                    totals = df[df["ROWSTATUS"] == 2]
                    if not totals.empty:
                        total_row = totals.iloc[-1]

                if total_row is None and "ROWORDER" in df.columns:
                    # Get the row with the largest ROWORDER (= grand total)
                    df_sorted = df.sort_values("ROWORDER", ascending=False)
                    total_row = df_sorted.iloc[0]

                if total_row is None:
                    total_row = df.iloc[-1]

                all_rows.append({
                    "date": day_str,
                    "commodity_code": code,
                    "commodity_name": METAL_LABELS.get(code, code),
                    "prev_warrant": safe_int(total_row.get("WRTWGHTS", 0)),
                    "today_warrant": safe_int(total_row.get("WRTQTY", 0)),
                    "warrant_change": safe_int(total_row.get("WRTCHANGE", 0)),
                })
                ok_flag = True

        elif isinstance(result, type(None)):
            skip += 1
            time.sleep(0.05)
            continue
        else:
            # Might be a DataFrame directly in newer akshare versions
            try:
                import pandas as pd
                if isinstance(result, pd.DataFrame) and not result.empty:
                    for _, row in result.iterrows():
                        var_name = str(row.get("VARNAME", "") or row.get("品种", ""))
                        code = cn_to_code(var_name)
                        if not code or (metals_filter and code not in metals_filter):
                            continue
                        all_rows.append({
                            "date": day_str,
                            "commodity_code": code,
                            "commodity_name": METAL_LABELS.get(code, code),
                            "prev_warrant": safe_int(row.get("WRTWGHTS", 0) or row.get("昨日仓单量", 0)),
                            "today_warrant": safe_int(row.get("WRTQTY", 0) or row.get("今日仓单量", 0)),
                            "warrant_change": safe_int(row.get("WRTCHANGE", 0) or row.get("增减", 0)),
                        })
            except Exception:
                pass

        ok += 1
        if ok <= 3 or ok % 50 == 0:
            day_data = [r for r in all_rows if r["date"] == day_str]
            info = ", ".join(f"{r['commodity_code']}={r['today_warrant']:,}" for r in day_data)
            print(f"  {progress} {day:%Y-%m-%d} ✓ {info}")

        time.sleep(delay)

    print(f"\n  Summary: {ok} days OK, {skip} skipped, {err} errors")
    return all_rows


# ══════════════════════════════════════════════════════════════════════════════
# MODE 2: Direct SHFE API (with full browser session emulation)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_via_direct(start_date: datetime, end_date: datetime,
                     metals_filter: set | None, delay: float) -> list:
    """Direct SHFE .dat API access with session/cookie handling."""
    import requests

    URL_PATTERNS = [
        "https://www.shfe.com.cn/data/dailydata/kx/dailystock{date}.dat",
        "http://www.shfe.com.cn/data/dailydata/kx/dailystock{date}.dat",
        "https://www.shfe.com.cn/data/dailydata/ck/dailystock{date}.dat",
    ]

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.shfe.com.cn/",
        "Origin": "https://www.shfe.com.cn",
        "X-Requested-With": "XMLHttpRequest",
    })

    # Warm up session with main page to get cookies
    print("\n  Warming up session (loading SHFE homepage)...")
    try:
        session.get("https://www.shfe.com.cn/", timeout=15)
    except Exception:
        pass

    # Probe for working URL pattern
    print("  Probing API endpoints...")
    working_pattern = None
    test_dates = []
    d = datetime.now()
    for _ in range(30):
        d -= timedelta(days=1)
        if d.weekday() < 5:
            test_dates.append(d)
        if len(test_dates) >= 10:
            break

    for pattern in URL_PATTERNS:
        for td in test_dates[:5]:
            url = pattern.format(date=td.strftime("%Y%m%d"))
            try:
                r = session.get(url, timeout=15)
                if r.status_code == 200:
                    text = r.content.decode("utf-8-sig", errors="ignore")
                    if "o_cursor" in text or "VARNAME" in text:
                        working_pattern = pattern
                        print(f"  ✓ Found: {pattern}")
                        break
                elif r.status_code == 403:
                    print(f"  ✗ 403 Forbidden on {pattern}")
                    break
            except requests.RequestException as e:
                print(f"  ✗ Connection error: {e}")
                break
        if working_pattern:
            break

    if not working_pattern:
        print("\n  ✗ All SHFE API endpoints blocked or unreachable.")
        print("  This typically happens when accessing from outside China.")
        print("\n  Solutions:")
        print("  1. Use default akshare mode (remove --direct flag)")
        print("  2. Use a VPN with a China endpoint")
        print("  3. Run this script from a server in China")
        sys.exit(1)

    # Fetch data
    trading_days = [start_date + timedelta(days=i)
                    for i in range((end_date - start_date).days + 1)
                    if (start_date + timedelta(days=i)).weekday() < 5]

    print(f"\n  Weekdays to check: {len(trading_days)}")

    all_rows = []
    ok = skip = err = 0

    for i, day in enumerate(trading_days):
        url = working_pattern.format(date=day.strftime("%Y%m%d"))
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                skip += 1
                time.sleep(0.1)
                continue
            text = resp.content.decode("utf-8-sig", errors="ignore").strip()
            if not text or len(text) < 50:
                skip += 1
                continue
            data = json.loads(text)
        except Exception:
            skip += 1
            time.sleep(0.1)
            continue

        cursor = data.get("o_cursor", [])
        if not cursor:
            for k, v in data.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    cursor = v
                    break

        if not cursor:
            skip += 1
            continue

        # Parse totals
        totals = {}
        for rec in cursor:
            code = cn_to_code(str(rec.get("VARNAME", "")))
            if not code or (metals_filter and code not in metals_filter):
                continue
            rs = rec.get("ROWSTATUS")
            ro = rec.get("ROWORDER", 0)
            if rs == 2 or (isinstance(ro, (int, float)) and ro >= 200000):
                wq = safe_int(rec.get("WRTQTY"))
                ww = safe_int(rec.get("WRTWGHTS"))
                wc = safe_int(rec.get("WRTCHANGE"))
                if code not in totals or wq > totals[code]["wrtqty"]:
                    totals[code] = {"wrtqty": wq, "wrtwghts": ww, "wrtchange": wc}

        day_str = day.strftime("%Y-%m-%d")
        for code in sorted(totals):
            t = totals[code]
            all_rows.append({
                "date": day_str,
                "commodity_code": code,
                "commodity_name": METAL_LABELS.get(code, code),
                "prev_warrant": t["wrtwghts"],
                "today_warrant": t["wrtqty"],
                "warrant_change": t["wrtchange"],
            })

        ok += 1
        if ok <= 3 or ok % 50 == 0:
            day_data = [r for r in all_rows if r["date"] == day_str]
            info = ", ".join(f"{r['commodity_code']}={r['today_warrant']:,}" for r in day_data)
            print(f"  [{i+1}/{len(trading_days)}] {day:%Y-%m-%d} ✓ {info}")

        time.sleep(delay)

    print(f"\n  Summary: {ok} days OK, {skip} skipped, {err} errors")
    return all_rows


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="SHFE Daily Warrant Scraper v3")
    parser.add_argument("--from", dest="from_date", type=str, default=None,
                        help="Start date YYYY-MM-DD (default: 1 year ago)")
    parser.add_argument("--to", dest="to_date", type=str, default=None,
                        help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--metal", type=str, default="CU",
                        help="Comma-separated: CU,AL,ZN,... (default: CU)")
    parser.add_argument("--all", action="store_true", help="All commodities")
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Seconds between requests (default: 0.5)")
    parser.add_argument("--direct", action="store_true",
                        help="Use direct SHFE API instead of akshare")

    args = parser.parse_args()

    end_date = datetime.now()
    if args.to_date:
        end_date = datetime.strptime(args.to_date, "%Y-%m-%d")
    start_date = end_date - timedelta(days=365)
    if args.from_date:
        start_date = datetime.strptime(args.from_date, "%Y-%m-%d")

    metals = None if args.all else set(m.strip().upper() for m in args.metal.split(","))
    metal_label = "ALL" if args.all else args.metal.upper()

    output_path = args.output or (
        f"shfe_daily_warrant_{metal_label}_"
        f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
    )

    mode = "direct" if args.direct else "akshare"

    print(f"\n{'=' * 65}")
    print(f"  SHFE Daily Warrant Scraper v3")
    print(f"{'=' * 65}")
    print(f"  Period : {start_date:%Y-%m-%d} ~ {end_date:%Y-%m-%d}")
    print(f"  Metals : {metal_label}")
    print(f"  Mode   : {mode}")
    print(f"  Output : {output_path}")
    print(f"  Delay  : {args.delay}s")
    print(f"{'=' * 65}")

    if mode == "akshare":
        all_rows = fetch_via_akshare(start_date, end_date, metals, args.delay)
    else:
        all_rows = fetch_via_direct(start_date, end_date, metals, args.delay)

    if not all_rows:
        print("\n  ERROR: No data collected.")
        if mode == "direct":
            print("  Try without --direct flag to use akshare instead.")
        else:
            print("  Check akshare version: pip install akshare --upgrade")
            print("  Try a recent date range first: --from 2024-01-01")
        sys.exit(1)

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[
            "date", "commodity_code", "commodity_name",
            "prev_warrant", "today_warrant", "warrant_change"])
        w.writeheader()
        w.writerows(all_rows)

    print(f"\n  Output: {output_path} ({len(all_rows):,} rows)")
    for code in sorted(set(r["commodity_code"] for r in all_rows)):
        vals = [r["today_warrant"] for r in all_rows if r["commodity_code"] == code]
        print(f"  {code} ({METAL_LABELS.get(code, code)}): {len(vals)} days, "
              f"range {min(vals):>8,} ~ {max(vals):>8,}")
    print(f"\n  Done! ✓\n")


if __name__ == "__main__":
    main()
