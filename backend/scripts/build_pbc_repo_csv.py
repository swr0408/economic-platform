"""
PBOC公开市场逆回购操作公告 → CSV化スクリプト
対象: https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/
出力: pbc_reverse_repo.csv (日付降順, 利率, 投标量, 中标量)

使い方:
  pip install requests beautifulsoup4
  python build_pbc_repo_csv.py
"""
import re, time, csv
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# ===== 設定 =====
BASE = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"
MAX_PAGE = 183
OUT_CSV = "pbc_reverse_repo.csv"
SLEEP = 0.4  # リクエスト間隔(秒)
ONLY_7D = False  # True にすると7日物のみ抽出

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ===== URL生成 =====
def list_url(page):
    return urljoin(BASE, "index.html") if page == 1 else urljoin(BASE, f"17081-{page}.html")

# ===== 正規表現 =====
re_date = re.compile(r"(\d{4}-\d{2}-\d{2})")
re_rate = re.compile(r"操作利率[：:\s]*([0-9.]+)\s*%")
re_bid  = re.compile(r"投标量[：:\s]*([0-9.]+)\s*亿元")
re_win  = re.compile(r"中标量[：:\s]*([0-9.]+)\s*亿元")
re_tenor = re.compile(r"期限[：:\s]*(\d+)\s*天")
# 旧書式（表形式）: 金額 亿元 / N天 / 利率
re_old_table = re.compile(r"([0-9.]+)\s*亿元[^0-9]*?(\d+)\s*天[^0-9]*?([0-9.]+)\s*%?")
# 旧書式の中标加权平均利率
re_old_rate = re.compile(r"中标加权平均利率[：:\s]*([0-9.]+)")

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    time.sleep(SLEEP)
    return r.text

def parse_list_page(html):
    """一覧ページから (detail_url, date) を抽出"""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.find_all("a"):
        txt = a.get_text(strip=True)
        if "公开市场业务交易公告" not in txt:
            continue
        href = a.get("href", "")
        if not href:
            continue
        # 日付取得（親要素 or リンクテキスト周辺）
        parent_txt = a.parent.get_text(" ", strip=True) if a.parent else txt
        m = re_date.search(parent_txt)
        if not m:
            continue
        dt = m.group(1)
        detail_url = urljoin("https://www.pbc.gov.cn", href) if href.startswith("/") else urljoin(BASE, href)
        items.append((detail_url, dt))
    return items

def parse_detail(html, dt):
    """詳細ページから (date, rate, bid, win) を返す。逆回购がなければ None"""
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)

    if "逆回购" not in text:
        return None

    # --- 新書式（2015年頃〜）---
    m_rate = re_rate.search(text)
    m_bid = re_bid.search(text)
    m_win = re_win.search(text)
    m_ten = re_tenor.search(text)

    if m_rate and (m_bid or m_win):
        if ONLY_7D and m_ten and int(m_ten.group(1)) != 7:
            return None
        rate = float(m_rate.group(1))
        bid = float(m_bid.group(1)) if m_bid else ""
        win = float(m_win.group(1)) if m_win else ""
        return (dt, rate, bid, win)

    # --- 旧書式（表形式: 金額/期限/利率）---
    triples = re_old_table.findall(text)
    if triples:
        chosen = None
        for amt, tenor, rate in triples:
            if ONLY_7D and int(tenor) != 7:
                continue
            if int(tenor) == 7:
                chosen = (amt, tenor, rate)
                break
            if chosen is None:
                chosen = (amt, tenor, rate)
        if chosen:
            amt, tenor, rate = chosen
            return (dt, float(rate), "", float(amt))

    # --- フォールバック: 中标加权平均利率 だけでも取れる場合 ---
    m_old = re_old_rate.search(text)
    if m_old:
        return (dt, float(m_old.group(1)), "", "")

    return None

def main():
    rows = []
    seen = set()

    for page in range(1, MAX_PAGE + 1):
        url = list_url(page)
        print(f"[{page}/{MAX_PAGE}] {url}")
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  ⚠ 一覧取得失敗: {e}")
            continue

        for detail_url, dt in parse_list_page(html):
            if detail_url in seen:
                continue
            seen.add(detail_url)

            try:
                dhtml = fetch(detail_url)
                parsed = parse_detail(dhtml, dt)
                if parsed:
                    rows.append(parsed)
                    print(f"  ✓ {dt} rate={parsed[1]}")
            except Exception as e:
                print(f"  ⚠ {dt} 詳細取得失敗: {e}")

    rows.sort(key=lambda x: x[0], reverse=True)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["日付", "利率(%)", "投标量(億元)", "中标量(億元)"])
        w.writerows(rows)

    print(f"\n完了: {OUT_CSV} ({len(rows)}行)")

if __name__ == "__main__":
    main()
