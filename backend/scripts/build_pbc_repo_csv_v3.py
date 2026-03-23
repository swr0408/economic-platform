"""
PBOC公开市场逆回购操作公告 → CSV化スクリプト v3
修正: IDが7桁(/5828284/)と19桁(/2026022808481138943/)の両方に対応
修正: タイムアウト時リトライ追加

使い方:
  pip install requests beautifulsoup4
  python build_pbc_repo_csv_v3.py
"""
import re, time, csv
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# ===== 設定 =====
BASE = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"
PBC_ROOT = "https://www.pbc.gov.cn"
MAX_PAGE = 183
OUT_CSV = "pbc_reverse_repo.csv"
SLEEP = 0.3
ONLY_7D = False
MAX_RETRY = 3

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def list_url(page):
    return urljoin(BASE, "index.html") if page == 1 else urljoin(BASE, f"17081-{page}.html")

re_date = re.compile(r"(\d{4}-\d{2}-\d{2})")
# 7桁〜19桁のIDに対応（/125475/NNNNN/index.html）
re_detail_path = re.compile(r"/125475/\d{5,}/")

def fetch(url, retries=MAX_RETRY):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            time.sleep(SLEEP)
            return r.text
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries - 1:
                wait = (attempt + 1) * 5
                print(f"    リトライ {attempt+1}/{retries} ({wait}秒待機): {e}")
                time.sleep(wait)
            else:
                raise

def parse_list_page(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re_detail_path.search(href):
            continue
        td = a.find_parent("td")
        if not td:
            continue
        span = td.find("span", class_="hui12")
        if span:
            m = re_date.search(span.get_text(strip=True))
        else:
            m = re_date.search(td.get_text(" ", strip=True))
        if not m:
            continue
        dt = m.group(1)
        detail_url = urljoin(PBC_ROOT, href)
        items.append((detail_url, dt))
    return items

def normalize_text(html):
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", id="zoom") or soup.find("div", class_="zoom1")
    if not content:
        content = soup
    table_text = ""
    for tbl in content.find_all("table"):
        for tr in tbl.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            table_text += " ".join(cells) + "\n"
    plain_text = content.get_text("\n", strip=True)
    return plain_text, table_text

def parse_detail(html, dt):
    plain_text, table_text = normalize_text(html)
    combined = plain_text + "\n" + table_text

    if "逆回购" not in combined:
        return None

    # 表のセル結合テキストから: N天 D.DD% XXXX亿元 YYYY亿元
    for line in table_text.split("\n"):
        compact = re.sub(r'\s+', '', line)
        m = re.match(r'(\d+)天([\d.]+)%([\d.]+)亿元([\d.]+)亿元', compact)
        if m:
            tenor = int(m.group(1))
            rate = float(m.group(2))
            bid = float(m.group(3))
            win = float(m.group(4))
            if ONLY_7D and tenor != 7:
                continue
            return (dt, rate, bid, win)

    compact_all = re.sub(r'\s+', '', combined)

    # 操作利率/投标量/中标量
    m_rate = re.search(r'操作利率[：:]?([\d.]+)%', compact_all)
    m_bid = re.search(r'投标量[：:]?([\d.]+)亿元', compact_all)
    m_win = re.search(r'中标量[：:]?([\d.]+)亿元', compact_all)
    m_ten = re.search(r'期限[：:]?(\d+)天', compact_all)
    if m_rate and (m_bid or m_win):
        if ONLY_7D and m_ten and int(m_ten.group(1)) != 7:
            return None
        rate = float(m_rate.group(1))
        bid = float(m_bid.group(1)) if m_bid else ""
        win = float(m_win.group(1)) if m_win else ""
        return (dt, rate, bid, win)

    # 旧書式: N亿元 M天 X.XX
    triples = re.findall(r'([\d.]+)亿元(\d+)天([\d.]+)', compact_all)
    if triples:
        chosen = None
        for amt, tenor, rate in triples:
            t = int(tenor)
            if ONLY_7D and t != 7:
                continue
            if t == 7:
                chosen = (amt, tenor, rate)
                break
            if chosen is None:
                chosen = (amt, tenor, rate)
        if chosen:
            amt, tenor, rate = chosen
            return (dt, float(rate), "", float(amt))

    # 中标加权平均利率
    m_old = re.search(r'中标加权平均利率[：:]?([\d.]+)', compact_all)
    if m_old:
        return (dt, float(m_old.group(1)), "", "")

    # 冒頭テキスト: 开展了N亿元M天期逆回购
    m_intro = re.search(r'开展了([\d.]+)亿元(\d+)天期?逆回购', compact_all)
    if m_intro:
        win = float(m_intro.group(1))
        tenor = int(m_intro.group(2))
        if ONLY_7D and tenor != 7:
            return None
        rate_m = re.search(r'([\d.]+)%', compact_all)
        if rate_m:
            rate = float(rate_m.group(1))
            return (dt, rate, win, win)

    return None

def main():
    rows = []
    seen = set()
    fail_count = 0
    skip_count = 0

    for page in range(1, MAX_PAGE + 1):
        url = list_url(page)
        print(f"[{page}/{MAX_PAGE}] {url}")
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  ⚠ 一覧取得失敗: {e}")
            continue

        page_items = parse_list_page(html)
        if not page_items:
            print(f"  ⚠ リンク0件")

        for detail_url, dt in page_items:
            if detail_url in seen:
                continue
            seen.add(detail_url)

            try:
                dhtml = fetch(detail_url)
                parsed = parse_detail(dhtml, dt)
                if parsed:
                    rows.append(parsed)
                    print(f"  ✓ {dt} rate={parsed[1]} bid={parsed[2]} win={parsed[3]}")
                else:
                    skip_count += 1
                    if fail_count < 20:
                        fail_count += 1
                        print(f"  ✗ {dt} 逆回购なし/抽出失敗")
            except Exception as e:
                print(f"  ⚠ {dt} 詳細取得失敗: {e}")

    rows.sort(key=lambda x: x[0], reverse=True)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["日付", "利率(%)", "投标量(億元)", "中标量(億元)"])
        w.writerows(rows)

    print(f"\n完了: {OUT_CSV} ({len(rows)}行, スキップ={skip_count}件)")

if __name__ == "__main__":
    main()
