# explore_nikkei2.py
import requests, re

session = requests.Session()
# Visit main page first for cookies
session.get("https://indexes.nikkei.co.jp/en/nkave/archives/data?list=per",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)

# Try the form action URL with month/year params
for params in [
    {"list": "per", "year": "2025", "month": "1"},
    {"list": "per", "year": "2024", "month": "6"},
    {"list": "per", "month": "3", "year": "2026"},
]:
    url = "https://indexes.nikkei.co.jp/en/nkave/statistics/dataload"
    r = session.get(url, params=params, timeout=15,
                    headers={"User-Agent": "Mozilla/5.0",
                             "Referer": "https://indexes.nikkei.co.jp/en/nkave/archives/data?list=per"})
    print(f"Status: {r.status_code} | Size: {len(r.text):>6} | Params: {params}")
    if r.status_code == 200 and len(r.text) > 100:
        # Look for table rows
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.DOTALL)
        tds = re.findall(r'<td[^>]*>(.*?)</td>', r.text, re.DOTALL)
        print(f"  Table rows: {len(rows)}, TD cells: {len(tds)}")
        print(f"  First 300 chars: {r.text[:300]}")
        print()