import requests, time
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

urls = [
    ("2018-07-05", "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/3572149/index.html"),
    ("2017-06-15", "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/3307079/index.html"),
    ("2024-08-07", "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/5425164/index.html"),
]

for dt, url in urls:
    print(f"\n{'='*50}")
    print(f"{dt}: {url}")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.encoding = r.apparent_encoding
    time.sleep(0.5)
    soup = BeautifulSoup(r.text, "html.parser")
    content = soup.find("div", id="zoom") or soup.find("div", class_="zoom1") or soup
    
    print(f"本文: {content.get_text(chr(10), strip=True)[:400]}")
    
    tables = content.find_all("table")
    print(f"テーブル数: {len(tables)}")
    for tbl in tables:
        rows = tbl.find_all("tr")
        print(f"  行数: {len(rows)}")
        for tr in rows[:4]:
            cells = [td.get_text(strip=True) for td in tr.find_all(["td","th"])]
            print(f"  cells: {cells}")
