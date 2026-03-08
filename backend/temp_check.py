import requests, pandas as pd, io

url = "https://www.stats.govt.nz/assets/Uploads/Labour-market-statistics/Labour-market-statistics-December-2025-quarter/Download-data/household-labour-force-survey-december-2025-quarter.xlsx"
resp = requests.get(url, timeout=120)
xls = pd.ExcelFile(io.BytesIO(resp.content))

print(f"All sheets: {xls.sheet_names}")

# Search ALL sheets for S1F3S (unemployment rate series code)
for sheet in xls.sheet_names:
    df = pd.read_excel(io.BytesIO(resp.content), sheet_name=sheet, header=None)
    for row in range(min(20, df.shape[0])):
        for col in range(min(25, df.shape[1])):
            val = df.iloc[row, col]
            if pd.notna(val) and isinstance(val, str) and 's1f3s' in val.lower():
                print(f"  Sheet '{sheet}' Row {row}, Col {col}: {val}")

# Also check Table 7 and Table 8 structure more carefully for unemployment rate
for target_sheet in ['Table 7', 'Table 8', 'Table 9', 'Table 10']:
    if target_sheet not in xls.sheet_names:
        print(f"\n{target_sheet}: NOT FOUND")
        continue
    df = pd.read_excel(io.BytesIO(resp.content), sheet_name=target_sheet, header=None)
    print(f"\n=== {target_sheet} (shape: {df.shape}) ===")
    # Show all header rows (first 12 rows)
    for row in range(min(12, df.shape[0])):
        vals = []
        for col in range(min(25, df.shape[1])):
            val = df.iloc[row, col]
            if pd.notna(val):
                vals.append(f"Col{col}={val}")
        if vals:
            print(f"  Row {row}: {', '.join(vals)}")
    # Show first 3 data rows
    for row in range(12, min(16, df.shape[0])):
        vals = []
        for col in range(min(25, df.shape[1])):
            val = df.iloc[row, col]
            if pd.notna(val):
                vals.append(f"Col{col}={val}")
        if vals:
            print(f"  Row {row}: {', '.join(vals)}")
    # Show last 3 data rows
    for row in range(max(12, df.shape[0]-4), df.shape[0]):
        vals = []
        for col in range(min(25, df.shape[1])):
            val = df.iloc[row, col]
            if pd.notna(val):
                vals.append(f"Col{col}={val}")
        if vals:
            print(f"  Row {row}: {', '.join(vals)}")
