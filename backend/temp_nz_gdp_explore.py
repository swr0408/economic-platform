import requests
import pandas as pd
import sys
import os
import re

filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cache', 'newzealand', 'nz_gdp_temp.xlsx')
os.makedirs(os.path.dirname(filepath), exist_ok=True)

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

urls = [
    'https://www.stats.govt.nz/assets/Uploads/Gross-domestic-product/Gross-domestic-product-September-2024-quarter/Download-data/gross-domestic-product-september-2024-quarter-supplementary-tables.xlsx',
    'https://www.stats.govt.nz/assets/Uploads/Gross-domestic-product/Gross-domestic-product-March-2025-quarter/Download-data/gross-domestic-product-march-2025-quarter-supplementary-tables.xlsx',
    'https://www.stats.govt.nz/assets/Uploads/Gross-domestic-product/Gross-domestic-product-December-2024-quarter/Download-data/gross-domestic-product-december-2024-quarter-supplementary-tables.xlsx',
    'https://www.stats.govt.nz/assets/Uploads/Gross-domestic-product/Gross-domestic-product-June-2024-quarter/Download-data/gross-domestic-product-june-2024-quarter-supplementary-tables.xlsx',
    'https://www.stats.govt.nz/assets/Uploads/Gross-domestic-product/Gross-domestic-product-September-2024-quarter/Download-data/gross-domestic-product-september-2024-quarter.xlsx',
    'https://www.stats.govt.nz/assets/Uploads/Gross-domestic-product/Gross-domestic-product-March-2025-quarter/Download-data/gross-domestic-product-march-2025-quarter.xlsx',
]

downloaded = False
for url in urls:
    print(f'Trying: {url}')
    try:
        resp = requests.get(url, timeout=30, headers=headers)
        print(f'  Status: {resp.status_code}, Size: {len(resp.content)}')
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            print(f'  SUCCESS - Downloaded {len(resp.content)} bytes')
            downloaded = True
            break
    except Exception as e:
        print(f'  Error: {e}')

if not downloaded:
    print()
    print('Trying release pages for download links...')
    page_urls = [
        'https://www.stats.govt.nz/information-releases/gross-domestic-product-march-2025-quarter/',
        'https://www.stats.govt.nz/information-releases/gross-domestic-product-september-2024-quarter/',
        'https://www.stats.govt.nz/information-releases/gross-domestic-product-december-2024-quarter/',
    ]
    for page_url in page_urls:
        print(f'Checking page: {page_url}')
        try:
            resp = requests.get(page_url, timeout=30, headers=headers)
            print(f'  Page status: {resp.status_code}')
            if resp.status_code == 200:
                xlsx_pat = r'href=["]([^"]*\.xlsx[^"]*)["]'
                xlsx_links = re.findall(r'href=.([^"]*\.xlsx)', resp.text)
                csv_links = re.findall(r'href=.([^"]*\.csv)', resp.text)
                print(f'  xlsx links found: {len(xlsx_links)}')
                for lnk in xlsx_links[:10]:
                    print(f'    {lnk}')
                print(f'  csv links found: {len(csv_links)}')
                for lnk in csv_links[:10]:
                    print(f'    {lnk}')
                for link in xlsx_links[:5]:
                    full = link if link.startswith('http') else f'https://www.stats.govt.nz{link}'
                    print(f'  Downloading: {full}')
                    try:
                        r2 = requests.get(full, timeout=30, headers=headers)
                        if r2.status_code == 200 and len(r2.content) > 1000:
                            with open(filepath, 'wb') as f:
                                f.write(r2.content)
                            print(f'  SUCCESS - {len(r2.content)} bytes')
                            downloaded = True
                            break
                    except Exception as ex:
                        print(f'  DL Error: {ex}')
                if downloaded:
                    break
        except Exception as e:
            print(f'  Error: {e}')

if not downloaded:
    print('FAILED to download any file')
    sys.exit(1)

print()
print('=' * 80)
print('ANALYZING EXCEL FILE')
print('=' * 80)

xls = pd.ExcelFile(filepath)
sheet_names = xls.sheet_names
print(f'Sheet names ({len(sheet_names)}):')
for i, name in enumerate(sheet_names):
    print(f'  {i}: {name}')

pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 300)
pd.set_option('display.max_colwidth', 40)

for sheet_name in sheet_names:
    print()
    print('=' * 80)
    print(f'SHEET: {sheet_name}')
    print('=' * 80)
    try:
        df = pd.read_excel(filepath, sheet_name=sheet_name, header=None, nrows=20)
        print(f'Shape (first 20 rows): {df.shape}')
        subset = df.iloc[:15, :20]
        print(subset.to_string())

        df_full = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
        print(f'Full shape: {df_full.shape}')

        keywords = ['SNEQ', 'SG01RSC00B01', 'GDP', 'Gross domestic product',
                     'Production', 'Expenditure', 'Percentage', 'growth', 'percent',
                     'Chain volume', 'Actual', 'Seasonally']
        for kw in keywords:
            found = []
            for r in range(min(50, len(df_full))):
                for c in range(min(30, len(df_full.columns))):
                    val = str(df_full.iloc[r, c])
                    if kw.lower() in val.lower():
                        found.append((r, c, val[:100]))
            if found:
                print(f'  Keyword [{kw}]:')
                for r, c, v in found[:8]:
                    print(f'    Row {r}, Col {c}: {v}')
    except Exception as e:
        print(f'  Error: {e}')

print('Done!')
