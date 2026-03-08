"""AFRE + RMB Loans + GDP monthly analysis script (temp)"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- (1)(2) PBOC Excel: AFRE total flow + RMB loans (億元, single-month) ---
excel_data = {
    '2024-01': {'afre_flow': 64734, 'rmb_loans': 48401},
    '2024-02': {'afre_flow': 14959, 'rmb_loans': 9773},
    '2024-03': {'afre_flow': 48335, 'rmb_loans': 32920},
    '2024-04': {'afre_flow': -658,  'rmb_loans': 3349},
    '2024-05': {'afre_flow': 20623, 'rmb_loans': 8197},
    '2024-06': {'afre_flow': 32985, 'rmb_loans': 21927},
    '2024-07': {'afre_flow': 7707,  'rmb_loans': -808},
    '2024-08': {'afre_flow': 30323, 'rmb_loans': 10411},
    '2024-09': {'afre_flow': 37635, 'rmb_loans': 19742},
    '2024-10': {'afre_flow': 14120, 'rmb_loans': 2965},
    '2024-11': {'afre_flow': 23288, 'rmb_loans': 5216},
    '2024-12': {'afre_flow': 28537, 'rmb_loans': 8402},
    '2025-01': {'afre_flow': 70546, 'rmb_loans': 52194},
    '2025-02': {'afre_flow': 22331, 'rmb_loans': 6528},
    '2025-03': {'afre_flow': 58961, 'rmb_loans': 38234},
    '2025-04': {'afre_flow': 11599, 'rmb_loans': 884},
    '2025-05': {'afre_flow': 22900, 'rmb_loans': 5923},
    '2025-06': {'afre_flow': 42251, 'rmb_loans': 23600},
    '2025-07': {'afre_flow': 11307, 'rmb_loans': -4296},
    '2025-08': {'afre_flow': 25660, 'rmb_loans': 6253},
    '2025-09': {'afre_flow': 35296, 'rmb_loans': 16081},
    '2025-10': {'afre_flow': 8161,  'rmb_loans': -154},
}

# Nov/Dec 2025 + Jan 2026: AFRE total from cached data, RMB loans N/A
cached_supplement = {
    '2025-11': {'afre_flow': 24900, 'rmb_loans': None},
    '2025-12': {'afre_flow': 22100, 'rmb_loans': None},
    '2026-01': {'afre_flow': 72208, 'rmb_loans': None},
}

# Merge
all_data = {}
all_data.update(excel_data)
all_data.update(cached_supplement)

# --- (4) Nominal GDP: NBS quarterly data (億元) ---
# Single-quarter nominal GDP (not YTD)
nbs_gdp_quarterly = {
    '2023-Q1': 284997,
    '2023-Q2': 314539,
    '2023-Q3': 321567,
    '2023-Q4': 345517,
    '2024-Q1': 296299,
    '2024-Q2': 327362,
    '2024-Q3': 334827,
    '2024-Q4': 358893,
    '2025-Q1': 318489,
    '2025-Q2': 343660,
    '2025-Q3': 351230,
    '2025-Q4': 373500,
}

quarter_months = {
    'Q1': ['01', '02', '03'],
    'Q2': ['04', '05', '06'],
    'Q3': ['07', '08', '09'],
    'Q4': ['10', '11', '12'],
}

gdp_monthly = {}
for qkey, qval in nbs_gdp_quarterly.items():
    year, q = qkey.split('-')
    months = quarter_months[q]
    monthly_val = qval / 3.0
    for m in months:
        gdp_monthly[f'{year}-{m}'] = monthly_val

# 2026-01: use 2025-Q1 as proxy
gdp_monthly['2026-01'] = nbs_gdp_quarterly['2025-Q1'] / 3.0

# ============================================================
# Output table
# ============================================================
print('=' * 120)
print('(1)-(4) PBOC AFRE Flow + RMB Loans to Real Economy + Nominal GDP (monthly interpolated)')
print('=' * 120)
print('Unit: AFRE flow / RMB loans / GDP = 億元 (100M CNY), Ratios = %')
print()

header = f'{"Month":<10} {"AFRE_flow":>12} {"RMB_loans":>12} {"GDP_mo":>14} {"AFRE/GDP%":>10} {"RMB/GDP%":>10}'
print(header)
print('-' * 74)

for m in sorted(all_data.keys()):
    d = all_data[m]
    afre = d['afre_flow']
    rmb = d['rmb_loans']
    gdp = gdp_monthly.get(m)

    afre_s = f'{afre:>12,}' if afre is not None else f'{"N/A":>12}'
    rmb_s = f'{rmb:>12,}' if rmb is not None else f'{"N/A":>12}'
    gdp_s = f'{gdp:>14,.0f}' if gdp is not None else f'{"N/A":>14}'

    if afre is not None and gdp is not None and gdp > 0:
        ar = f'{afre / gdp * 100:>9.2f}%'
    else:
        ar = f'{"N/A":>10}'

    if rmb is not None and gdp is not None and gdp > 0:
        rr = f'{rmb / gdp * 100:>9.2f}%'
    else:
        rr = f'{"N/A":>10}'

    print(f'{m:<10} {afre_s} {rmb_s} {gdp_s} {ar} {rr}')

# Also show annualized (trailing 12M) ratios
print()
print('=' * 100)
print('Trailing 12-Month Sum / Annual GDP ratio')
print('=' * 100)
months_sorted = sorted(all_data.keys())
print(f'{"Month":<10} {"T12M_AFRE":>14} {"T12M_RMB":>14} {"T12M_GDP":>14} {"AFRE/GDP%":>10} {"RMB/GDP%":>10}')
print('-' * 80)

for i, m in enumerate(months_sorted):
    if i < 11:
        continue  # need 12 months of history
    last_12 = months_sorted[i-11:i+1]
    t12_afre = sum(all_data[mm]['afre_flow'] for mm in last_12 if all_data[mm]['afre_flow'] is not None)

    rmb_vals = [all_data[mm]['rmb_loans'] for mm in last_12 if all_data[mm]['rmb_loans'] is not None]
    t12_rmb = sum(rmb_vals) if len(rmb_vals) == 12 else None

    t12_gdp = sum(gdp_monthly.get(mm, 0) for mm in last_12)

    t12_afre_s = f'{t12_afre:>14,}'
    t12_rmb_s = f'{t12_rmb:>14,}' if t12_rmb is not None else f'{"N/A":>14}'
    t12_gdp_s = f'{t12_gdp:>14,.0f}'

    if t12_gdp > 0:
        ar = f'{t12_afre / t12_gdp * 100:>9.2f}%'
    else:
        ar = f'{"N/A":>10}'

    if t12_rmb is not None and t12_gdp > 0:
        rr = f'{t12_rmb / t12_gdp * 100:>9.2f}%'
    else:
        rr = f'{"N/A":>10}'

    print(f'{m:<10} {t12_afre_s} {t12_rmb_s} {t12_gdp_s} {ar} {rr}')

print()
print('Notes:')
print('  - (1) AFRE Flow: PBOC official single-month values (not stock diff)')
print('  - (2) RMB loans: "RMB loans to real economy" from AFRE Excel Col C')
print('       FMP "New Yuan Loans" is a DIFFERENT concept (all FI new loans)')
print('       2025-11 ~ 2026-01: PBOC Flow Excel not yet published for these months')
print('  - (3) AFRE Flow data is already single-month (NOT cumulative/YTD)')
print('       No differencing needed')
print('  - (4) GDP: NBS quarterly nominal, monthly by equal 1/3 split (no SA)')
print('       2026-01 uses 2025-Q1/3 as proxy')
