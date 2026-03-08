"""
デバッグv5: スキップされた年代の詳細ページ本文を確認
2025-03 (page 12-13), 2023 (page 30), 2019 (page 90), 2015 (page 120), 2010 (page 155), 2004 (page 183)
"""
import re, requests, time
from urllib.parse import urljoin
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"
PBC_ROOT = "https://www.pbc.gov.cn"
re_detail_path = re.compile(r"/125475/\d{5,}/")
re_date = re.compile(r"(\d{4}-\d{2}-\d{2})")

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    time.sleep(0.5)
    return r.text

# サンプルページから1件ずつ詳細を取得
sample_pages = [13, 30, 50, 87, 120, 155, 183]

for page_num in sample_pages:
    url = f"{BASE}17081-{page_num}.html"
    print(f"\n{'='*60}")
    print(f"PAGE {page_num}: {url}")
    print('='*60)

    try:
        html = fetch(url)
    except Exception as e:
        print(f"一覧取得失敗: {e}")
        continue

    soup = BeautifulSoup(html, "html.parser")
    
    # リンクと日付を取得
    items = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re_detail_path.search(href):
            continue
        td = a.find_parent("td")
        if not td:
            continue
        span = td.find("span", class_="hui12")
        dt = ""
        if span:
            m = re_date.search(span.get_text(strip=True))
            if m:
                dt = m.group(1)
        detail_url = urljoin(PBC_ROOT, href)
        items.append((detail_url, dt, a.get_text(strip=True)))

    print(f"リンク数: {len(items)}")
    if not items:
        # span.hui12だけ表示
        spans = soup.find_all("span", class_="hui12")
        print(f"span.hui12数: {len(spans)}")
        if spans:
            print(f"  最初: {spans[0].get_text(strip=True)}")
        continue

    # 最初の1件の詳細を取得
    detail_url, dt, title = items[0]
    print(f"詳細: {title} ({dt})")
    print(f"URL: {detail_url}")

    try:
        dhtml = fetch(detail_url)
    except Exception as e:
        print(f"詳細取得失敗: {e}")
        continue

    dsoup = BeautifulSoup(dhtml, "html.parser")
    content = dsoup.find("div", id="zoom") or dsoup.find("div", class_="zoom1")
    if content:
        body = content.get_text("\n", strip=True)
        print(f"本文 ({len(body)} chars):")
        print(body[:600])
        
        # テーブル内容
        tables = content.find_all("table")
        if tables:
            print(f"\nテーブル数: {len(tables)}")
            for tr in tables[0].find_all("tr")[:5]:
                cells = [td.get_text(strip=True) for td in tr.find_all(["td","th"])]
                print(f"  row: {cells}")
    else:
        body = dsoup.get_text("\n", strip=True)
        print(f"zoom div不在。全文 ({len(body)} chars):")
        print(body[:600])
