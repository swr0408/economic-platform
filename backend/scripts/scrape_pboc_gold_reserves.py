"""
中国人民銀行 金準備（Official Reserve Assets - Gold）
過去時系列スクレイピングスクリプト（1回のみ実行）

データソース: PBOC HTM ファイル
対象期間: 1999年12月〜2026年最新
出力: backend/data/cache/china/policy/cn_gold_reserves_cache.csv

3つの異なるHTMフォーマットに対応:
  Format A (1999): 単一月、「黄金储备（万盎司）」行
  Format B (2002-2015): 12ヶ月、「黄金储备（万盎司）」行（値=万盎司のみ）
  Format C (2016-2026): 12ヶ月、「4.黄金Gold」行（USD値）+ 次行で万盎司
"""
import csv
import re
import sys
import io
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Windows UTF-8 出力
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# URL → (year, format_type)
HTM_URLS = [
    # Format A: 1999 (Dec only)
    ("1999", "A", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/1999-S5c.htm"),
    # 2000-2001: データなし（PBOCに個別HTMファイルが見つからない）
    # → 1999年12月の値を2000-2001の各月にフォワードフィル
    # Format B: 2002-2015 (12ヶ月, 万盎司 only)
    ("2002", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2002S6.htm"),
    ("2003", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2003S6.htm"),
    ("2004", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2004S6.htm"),
    ("2005", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2005S6.htm"),
    ("2006", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2006S09.htm"),
    ("2007", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2007S09.htm"),
    ("2008", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2008S09.htm"),
    ("2009", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2009s09.htm"),
    ("2010", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2010s09.htm"),
    ("2011", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2011s09.htm"),
    ("2012", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2012s09.htm"),
    ("2013", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2013s09.htm"),
    ("2014", "B", "https://www.pbc.gov.cn/eportal/fileDir/defaultCurSite/resource/cms/2015/07/2014s09.htm"),
    ("2015", "B", "https://wuhan.pbc.gov.cn/diaochatongjisi/fileDir/resource/cms/2016/01/2016010716554214736.htm"),
    # Format C: 2016+ (USD + SDR + ounces)
    ("2016", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/fileDir/resource/cms/2017/01/2017010710465834913.htm"),
    ("2017", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/fileDir/resource/cms/2018/01/2018010714074812045.htm"),
    ("2018", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/fileDir/resource/cms/2019/01/2019010715590669664.htm"),
    ("2019", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/attachDir/2025/11/2025110513574179078.htm"),
    ("2020", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/attachDir/2025/11/2025110510211034974.htm"),
    ("2021", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/attachDir/2025/11/2025110510210650225.htm"),
    ("2022", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/attachDir/2025/11/2025110417063435178.htm"),
    ("2023", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/attachDir/2025/11/2025110416185712586.htm"),
    ("2024", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/attachDir/2025/11/2025111416370065184.htm"),
    ("2025", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/attachDir/2026/01/2026010715590077987.htm"),
    ("2026", "C", "https://wuhan.pbc.gov.cn/diaochatongjisi/attachDir/2026/03/2026030709594279635.htm"),
]


def _fetch_soup(url: str) -> BeautifulSoup:
    """URLからBeautifulSoupオブジェクトを取得（リトライ付き）"""
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200 or len(r.content) < 500:
            print(f"  [retry {attempt+1}] status={r.status_code}, len={len(r.content)}", end="")
            time.sleep(2)
            continue
        # content.decode で正しくエンコーディング処理
        for enc in ["utf-8", "utf-8-sig", "gb2312", "gbk", "gb18030"]:
            try:
                text = r.content.decode(enc)
                if "黄金" in text or "Gold" in text:
                    return BeautifulSoup(text, "html.parser")
            except (UnicodeDecodeError, LookupError):
                continue
        # フォールバック
        r.encoding = r.apparent_encoding or "utf-8"
        return BeautifulSoup(r.text, "html.parser")
    raise Exception(f"Failed to fetch after 3 retries: {url}")


def _extract_months_from_header(rows, year: str):
    """ヘッダー行から月のマッピング (col_index -> YYYY-MM-01) を抽出"""
    months = {}
    # 「项目」「Item」を含むヘッダー行のみを対象
    for row in rows[:10]:
        cells = row.find_all(["td", "th"])
        row_text = " ".join(c.get_text(strip=True) for c in cells)
        if "项目" not in row_text and "Item" not in row_text:
            continue
        for j, cell in enumerate(cells):
            text = cell.get_text(strip=True)
            # YYYY.MM format (month must be 01-12)
            m = re.match(r"(\d{4})\.(\d{1,2})$", text)
            if m:
                y, mo = int(m.group(1)), int(m.group(2))
                if 1 <= mo <= 12 and 1990 <= y <= 2099:
                    months[j] = f"{y}-{mo:02d}-01"
        if months:
            break
    return months


def _parse_ounces_value(text):
    """'7419万盎司' → 7419.0, or plain number '1608' → 1608.0"""
    text = text.strip().replace(",", "").replace(" ", "").replace("\xa0", "")
    m = re.search(r"([\d.]+)", text)
    if m:
        return float(m.group(1))
    return None


def _parse_usd_value(text):
    """'3695.82 ' → 3695.82 (亿美元)"""
    text = text.strip().replace(",", "").replace(" ", "").replace("\xa0", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_format_a(soup, year):
    """1999: 単一月（12月のみ）、黄金储备（万盎司）"""
    records = []
    table = soup.find("table")
    if not table:
        return records

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        text = " ".join(c.get_text(strip=True) for c in cells)
        if "黄金储备" in text and "万盎司" in text:
            for c in reversed(cells):
                val = _parse_ounces_value(c.get_text(strip=True))
                if val is not None:
                    records.append({
                        "date": f"{year}-12-01",
                        "gold_ounces_wan": val,
                        "gold_value_usd_yi": None,
                    })
                    break
            break
    return records


def parse_format_b(soup, year):
    """2002-2015: 12ヶ月、黄金储备（万盎司）のみ"""
    records = []
    table = soup.find("table")
    if not table:
        return records

    rows = table.find_all("tr")
    col_months = _extract_months_from_header(rows, year)

    if not col_months:
        # フォールバック: 列位置からマッピング
        for i in range(1, 13):
            col_months[i] = f"{year}-{i:02d}-01"

    for row in rows:
        cells = row.find_all(["td", "th"])
        row_text = " ".join(c.get_text(strip=True) for c in cells)
        if "黄金储备" in row_text and "万盎司" in row_text:
            for j, cell in enumerate(cells):
                if j in col_months:
                    val = _parse_ounces_value(cell.get_text(strip=True))
                    if val is not None:
                        records.append({
                            "date": col_months[j],
                            "gold_ounces_wan": val,
                            "gold_value_usd_yi": None,
                        })
            break
    return records


def parse_format_c(soup, year):
    """2016+: 12ヶ月、4.黄金Gold行（USD+SDR交互）+ 次行に万盎司"""
    records = []
    table = soup.find("table")
    if not table:
        return records

    rows = table.find_all("tr")
    col_months = _extract_months_from_header(rows, year)
    if not col_months:
        return records

    # Gold row を探す
    gold_row_idx = None
    for i, row in enumerate(rows):
        cells = row.find_all(["td", "th"])
        row_text = " ".join(c.get_text(strip=True) for c in cells)
        if re.search(r"4\.\s*黄金", row_text):
            gold_row_idx = i
            break

    if gold_row_idx is None:
        return records

    gold_cells = rows[gold_row_idx].find_all(["td", "th"])
    ounce_row = rows[gold_row_idx + 1] if gold_row_idx + 1 < len(rows) else None
    ounce_cells = ounce_row.find_all(["td", "th"]) if ounce_row else []

    # ヘッダーの月をソートして順番に処理
    sorted_months = sorted(col_months.items(), key=lambda x: x[0])

    for month_idx, (header_col, date_str) in enumerate(sorted_months):
        # データ行: cell 0 = label, then pairs: USD, SDR, USD, SDR, ...
        usd_col = month_idx * 2 + 1
        ounce_col = month_idx * 2 + 1

        usd_val = None
        ounce_val = None

        if usd_col < len(gold_cells):
            usd_val = _parse_usd_value(gold_cells[usd_col].get_text(strip=True))

        if ounce_col < len(ounce_cells):
            ounce_val = _parse_ounces_value(ounce_cells[ounce_col].get_text(strip=True))

        if usd_val is not None or ounce_val is not None:
            records.append({
                "date": date_str,
                "gold_ounces_wan": ounce_val,
                "gold_value_usd_yi": usd_val,
            })

    return records


def main():
    output_dir = Path(__file__).parent.parent / "data" / "cache" / "china" / "policy"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "cn_gold_reserves_cache.csv"

    all_records = []

    for year, fmt, url in HTM_URLS:
        print(f"Fetching {year} (format {fmt})...", end=" ", flush=True)
        try:
            soup = _fetch_soup(url)

            if fmt == "A":
                records = parse_format_a(soup, year)
            elif fmt == "B":
                records = parse_format_b(soup, year)
            elif fmt == "C":
                records = parse_format_c(soup, year)
            else:
                records = []

            print(f"{len(records)} records")
            if not records:
                print(f"  WARNING: No records for {year}!")
            all_records.extend(records)
            time.sleep(1.5)  # Rate limit avoidance

        except Exception as e:
            print(f"ERROR: {e}")

    # 2000-2001: forward fill from 1999-12 value
    dec_1999 = None
    for rec in all_records:
        if rec["date"] == "1999-12-01":
            dec_1999 = rec["gold_ounces_wan"]
            break

    if dec_1999:
        for year in [2000, 2001]:
            for month in range(1, 13):
                all_records.append({
                    "date": f"{year}-{month:02d}-01",
                    "gold_ounces_wan": dec_1999,
                    "gold_value_usd_yi": None,
                })
        print(f"Added 24 forward-filled records for 2000-2001 (ounces={dec_1999})")

    # 日付でソート＋重複排除
    seen = set()
    unique_records = []
    for rec in sorted(all_records, key=lambda x: x["date"]):
        if rec["date"] not in seen:
            seen.add(rec["date"])
            unique_records.append(rec)

    # CSV出力
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "gold_ounces_wan", "gold_value_usd_yi"])
        writer.writeheader()
        for rec in unique_records:
            writer.writerow(rec)

    print(f"\nTotal: {len(unique_records)} records")
    print(f"Range: {unique_records[0]['date']} ~ {unique_records[-1]['date']}")
    print(f"Output: {output_file}")

    # サマリー表示
    print("\nSample (first 5):")
    for rec in unique_records[:5]:
        print(f"  {rec['date']}: ounces={rec['gold_ounces_wan']}, usd={rec['gold_value_usd_yi']}")
    print("Sample (last 5):")
    for rec in unique_records[-5:]:
        print(f"  {rec['date']}: ounces={rec['gold_ounces_wan']}, usd={rec['gold_value_usd_yi']}")

    # Gap check
    print("\nYear coverage check:")
    dates = [r["date"] for r in unique_records]
    for y in range(1999, 2027):
        count = sum(1 for d in dates if d.startswith(str(y)))
        if count == 0:
            print(f"  {y}: MISSING!")
        elif count < 12 and y != 1999 and y != 2026:
            print(f"  {y}: only {count} months")
        else:
            print(f"  {y}: {count} months OK")


if __name__ == "__main__":
    main()
