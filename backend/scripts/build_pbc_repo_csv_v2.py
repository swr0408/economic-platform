"""
PBOC公开市场逆回购操作公告 → CSV化スクリプト v2
修正: 日付はgrandparent<td>内の<span class="hui12">から取得
修正: 詳細ページの利率等はHTML表で分割されているため正規化してから解析
修正: 古い公告はリンクテキストが異なる場合があるので広めに拾う

使い方:
  pip install requests beautifulsoup4
  python build_pbc_repo_csv_v2.py
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
ONLY_7D = False  # True で7日物のみ

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def list_url(page):
    return urljoin(BASE, "index.html") if page == 1 else urljoin(BASE, f"17081-{page}.html")

re_date = re.compile(r"(\d{4}-\d{2}-\d{2})")
re_detail_path = re.compile(r"/\d{10,}/")

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    time.sleep(SLEEP)
    return r.text

def parse_list_page(html):
    """一覧ページから (detail_url, date) を抽出
    構造: <td><font class="newslist_style"><a href="...">タイトル</a></font><span class="hui12">YYYY-MM-DD</span></td>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re_detail_path.search(href):
            continue
        # grandparent = <td> から日付を取る
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
    """詳細ページの本文を取得し、HTML表による分割（1.\n40\n%）を正規化"""
    soup = BeautifulSoup(html, "html.parser")
    # zoom divから取る
    content = soup.find("div", id="zoom") or soup.find("div", class_="zoom1")
    if not content:
        content = soup

    # テーブル内のセルを連結して1行にする
    # 方法: 全<td>/<th>のテキストをスペース区切りで結合
    tables = content.find_all("table")
    table_text = ""
    for tbl in tables:
        for tr in tbl.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            table_text += " ".join(cells) + "\n"

    # テーブル以外のテキスト
    plain_text = content.get_text("\n", strip=True)

    return plain_text, table_text

def parse_detail(html, dt):
    """詳細ページから逆回购の (date, rate, bid, win) を返す"""
    plain_text, table_text = normalize_text(html)
    combined = plain_text + "\n" + table_text

    if "逆回购" not in combined:
        return None

    # === 表のセル結合テキストから抽出（新書式） ===
    # 表ヘッダ行: 期限 操作利率 投标量 中标量 (or similar)
    # データ行:   7天 1.40% 1160亿元 1160亿元
    # セル結合後: "7天 1.40% 1160亿元 1160亿元" or "7 天 1. 40 % 1160 亿元 1160 亿元"

    # table_text の各行をチェック
    for line in table_text.split("\n"):
        # 数字+天 ... 数字+% ... 数字+亿元 ... 数字+亿元 のパターン
        # セル区切りのスペースを除去して連結
        compact = re.sub(r'\s+', '', line)
        # パターン: N天D.DD%XXXX亿元YYYY亿元
        m = re.match(
            r'(\d+)天([\d.]+)%([\d.]+)亿元([\d.]+)亿元',
            compact
        )
        if m:
            tenor = int(m.group(1))
            rate = float(m.group(2))
            bid = float(m.group(3))
            win = float(m.group(4))
            if ONLY_7D and tenor != 7:
                continue
            return (dt, rate, bid, win)

    # === プレーンテキストから抽出（古い書式、表がない場合）===
    compact_all = re.sub(r'\s+', '', combined)

    # パターン1: 操作利率X.XX% (新書式のテキスト版)
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

    # パターン2: 旧書式テーブル（招标数量/期限品种/中标加权平均利率）
    # compact_all から: N亿元M天X.XX のパターン
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

    # パターン3: 中标加权平均利率だけ
    m_old = re.search(r'中标加权平均利率[：:]?([\d.]+)', compact_all)
    if m_old:
        return (dt, float(m_old.group(1)), "", "")

    # パターン4: 冒頭テキストから金額と利率を拾う
    # 例: "开展了1160亿元7天期逆回购操作" + 表から利率
    m_intro = re.search(r'开展了([\d.]+)亿元(\d+)天期?逆回购', compact_all)
    if m_intro:
        win = float(m_intro.group(1))
        tenor = int(m_intro.group(2))
        if ONLY_7D and tenor != 7:
            return None
        # 利率を探す
        rate_m = re.search(r'([\d.]+)%', compact_all)
        if rate_m:
            rate = float(rate_m.group(1))
            return (dt, rate, win, win)

    return None

def main():
    rows = []
    seen = set()
    fail_count = 0

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
                    fail_count += 1
                    if fail_count <= 10:
                        print(f"  ✗ {dt} 逆回购データ抽出失敗 (URL: {detail_url})")
            except Exception as e:
                print(f"  ⚠ {dt} 詳細取得失敗: {e}")

    rows.sort(key=lambda x: x[0], reverse=True)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["日付", "利率(%)", "投标量(億元)", "中标量(億元)"])
        w.writerows(rows)

    print(f"\n完了: {OUT_CSV} ({len(rows)}行, 抽出失敗={fail_count}件)")

if __name__ == "__main__":
    main()
