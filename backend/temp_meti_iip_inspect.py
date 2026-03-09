import requests
import pandas as pd
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 1. 2018年1月～ (current base year 2020)
url1 = 'https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_gom1j.xlsx'
print("=" * 80)
print(f"Fetching: {url1}")
print("=" * 80)

session = requests.Session()
session.headers.update(headers)

for attempt in range(3):
    try:
        print(f"Attempt {attempt + 1}...")
        resp1 = session.get(url1, timeout=120)
        print(f"Status: {resp1.status_code}, Size: {len(resp1.content)} bytes")
        break
    except Exception as e:
        print(f"Attempt {attempt + 1} failed: {e}")
        if attempt == 2:
            print("All attempts failed. Exiting.")
            sys.exit(1)
        import time
        time.sleep(5)

xls1 = pd.ExcelFile(io.BytesIO(resp1.content))
print(f"Sheet names: {xls1.sheet_names}")

# Read the first sheet to understand structure
for sheet in xls1.sheet_names[:3]:
    print(f"\n--- Sheet: {sheet} ---")
    df = pd.read_excel(io.BytesIO(resp1.content), sheet_name=sheet, header=None)
    print(f"Shape: {df.shape}")
    # Print first 20 rows to understand structure
    for row in range(min(20, df.shape[0])):
        vals = []
        for col in range(min(15, df.shape[1])):
            val = df.iloc[row, col]
            if pd.notna(val):
                vals.append(f"Col{col}={val}")
        if vals:
            print(f"  Row {row}: {', '.join(vals)}")

# Look for '電子部品' in all sheets
print("\n" + "=" * 80)
print("Searching for '電子部品' across all sheets...")
print("=" * 80)

for sheet in xls1.sheet_names:
    df = pd.read_excel(io.BytesIO(resp1.content), sheet_name=sheet, header=None)
    for row in range(df.shape[0]):
        for col in range(df.shape[1]):
            val = df.iloc[row, col]
            if pd.notna(val) and isinstance(val, str) and '電子部品' in val:
                print(f"  Sheet={sheet}, Row={row}, Col={col}: {val}")
                # Show surrounding context
                for c in range(min(15, df.shape[1])):
                    v = df.iloc[row, c]
                    if pd.notna(v):
                        print(f"    Col{c}: {v}")
                break

print("\nDone!")
