"""
PBOC公开市場逆回購操作公告 → CSV化スクリプト v4
全年代対応: テーブルをセル単位で解析

テーブル書式の年代別バリエーション:
  2025/3〜   : 期限 | 操作量   | 操作利率  (投标量/中标量は別欄の場合あり)
  2019〜2025/3: 期限 | 中标量   | 中标利率
  2016頃     : 期限 | 交易量   | 中标利率   (7天/14天/28天 複数行)
  2004〜     : 正回購・央行票据の場合は逆回購ではないのでスキップ

使い方:
  pip install requests beautifulsoup4
  python build_pbc_repo_csv_v4.py
"""
import re, time, csv
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

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
re_detail_path = re.compile(r"/125475/\d{5,}/")
re_num = re.compile(r"([\d.]+)")

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
                print(f"    リトライ {attempt+1}/{retries} ({wait}秒待機)")
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

def extract_number(text):
    """テキストから数値を抽出: '2685亿元' -> 2685.0, '1.50%' -> 1.5"""
    m = re_num.search(text.replace(",", "").replace("，", ""))
    return float(m.group(1)) if m else None

def parse_detail(html, dt):
    """詳細ページから逆回購データを抽出
    テーブルのヘッダー行からカラムの意味を判定し、データ行から値を取る
    """
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", id="zoom") or soup.find("div", class_="zoom1") or soup
    full_text = content.get_text("", strip=True)

    # 逆回購が含まれていない公告はスキップ（正回購、央行票据、不开展等）
    if "逆回购" not in full_text:
        return None
    if "不开展逆回购" in full_text or "不开展 逆回购" in full_text:
        return None

    # テーブルを探す
    tables = content.find_all("table")
    for tbl in tables:
        rows = tbl.find_all("tr")
        if len(rows) < 2:
            continue

        # ヘッダー行のセルテキスト
        header_cells = [td.get_text(strip=True) for td in rows[0].find_all(["td", "th"])]
        if not header_cells:
            continue

        # ヘッダーからカラムの役割を判定
        col_map = {}  # role -> column_index
        for i, h in enumerate(header_cells):
            h_clean = h.replace("\n", "").replace(" ", "")
            if "期限" in h_clean:
                col_map["tenor"] = i
            elif "操作量" in h_clean or "投标量" in h_clean:
                col_map["bid"] = i
            elif "中标量" in h_clean or "交易量" in h_clean:
                col_map["win"] = i
            elif "操作利率" in h_clean or "中标利率" in h_clean:
                col_map["rate"] = i

        if "rate" not in col_map:
            continue

        # ボリューム列: bid/win のどちらかしかない場合もある
        # 操作量 → bid=win (固定利率方式)
        # 中标量 → win
        # 交易量 → win
        # 投标量+中标量 → 両方

        # データ行を解析
        for data_row in rows[1:]:
            cells = [td.get_text(strip=True) for td in data_row.find_all(["td", "th"])]
            if len(cells) <= max(col_map.values()):
                continue

            # 期限チェック
            tenor_text = cells[col_map["tenor"]] if "tenor" in col_map else ""
            tenor_num = extract_number(tenor_text)
            if tenor_num is not None:
                if ONLY_7D and int(tenor_num) != 7:
                    continue

            rate = extract_number(cells[col_map["rate"]])
            if rate is None:
                continue

            bid = ""
            win = ""
            if "bid" in col_map and "win" in col_map:
                bid = extract_number(cells[col_map["bid"]]) or ""
                win = extract_number(cells[col_map["win"]]) or ""
            elif "bid" in col_map:
                # 操作量のみ → bid=win
                val = extract_number(cells[col_map["bid"]])
                bid = val or ""
                win = val or ""
            elif "win" in col_map:
                # 中标量/交易量のみ
                win = extract_number(cells[col_map["win"]]) or ""

            return (dt, rate, bid, win)

    # テーブルが見つからない場合、テキストからフォールバック
    compact = re.sub(r'\s+', '', full_text)

    # 冒頭テキスト: 开展了N亿元M天期逆回购
    m_intro = re.search(r'开展了([\d.]+)亿元(\d+)天期?逆回购', compact)
    if m_intro:
        win = float(m_intro.group(1))
        tenor = int(m_intro.group(2))
        if ONLY_7D and tenor != 7:
            return None
        rate_m = re.search(r'([\d.]+)%', compact)
        if rate_m:
            rate = float(rate_m.group(1))
            return (dt, rate, win, win)

    return None

def main():
    rows = []
    seen = set()
    skip_count = 0
    err_count = 0

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
            except Exception as e:
                err_count += 1
                if err_count <= 5:
                    print(f"  ⚠ {dt} 詳細取得失敗: {e}")

    rows.sort(key=lambda x: x[0], reverse=True)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["日付", "利率(%)", "投标量(億元)", "中标量(億元)"])
        w.writerows(rows)

    print(f"\n完了: {OUT_CSV} ({len(rows)}行, スキップ={skip_count}件, エラー={err_count}件)")

if __name__ == "__main__":
    main()
