"""
中国財政部「地方政府债券发行和债务余额情况」からデータをスクレイピングしてCSVを作成するスクリプト

対象期間: 2021年10月 ~ 2025年9月
データソース: https://yss.mof.gov.cn/zhuantilanmu/dfzgl/sjtj/
"""

import requests
import re
import csv
import time
import sys
import os
from bs4 import BeautifulSoup

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "https://yss.mof.gov.cn/zhuantilanmu/dfzgl/sjtj/"

# All report URLs collected from index pages
REPORTS = [
    # 2021
    ("2021/10", "202111/t20211123_3767948.htm"),
    ("2021/11", "202202/t20220209_3786602.htm"),
    ("2021/12", "202202/t20220209_3786613.htm"),
    # 2022
    ("2022/1",  "202203/t20220322_3797108.htm"),
    ("2022/2",  "202203/t20220322_3797112.htm"),
    ("2022/3",  "202205/t20220518_3811261.htm"),
    ("2022/4",  "202205/t20220518_3811310.htm"),
    ("2022/5",  "202206/t20220630_3823574.htm"),
    ("2022/6",  "202207/t20220726_3829548.htm"),
    ("2022/7",  "202209/t20220930_3844165.htm"),
    ("2022/8",  "202209/t20220930_3844166.htm"),
    ("2022/9",  "202211/t20221103_3849441.htm"),
    ("2022/10", "202211/t20221130_3854835.htm"),
    ("2022/11", "202212/t20221229_3861047.htm"),
    ("2022/12", "202301/t20230128_3864087.htm"),
    # 2023
    ("2023/1",  "202302/t20230227_3868366.htm"),
    ("2023/2",  "202303/t20230327_3874744.htm"),
    ("2023/3",  "202304/t20230426_3881032.htm"),
    ("2023/4",  "202305/t20230529_3887551.htm"),
    ("2023/5",  "202306/t20230628_3893293.htm"),
    ("2023/6",  "202307/t20230728_3899191.htm"),
    ("2023/7",  "202308/t20230829_3904518.htm"),
    ("2023/8",  "202309/t20230926_3909090.htm"),
    ("2023/9",  "202310/t20231027_3913516.htm"),
    ("2023/10", "202311/t20231129_3918545.htm"),
    ("2023/11", "202312/t20231225_3923816.htm"),
    ("2023/12", "202401/t20240130_3927707.htm"),
    # 2024
    ("2024/1",  "202402/t20240229_3929677.htm"),
    ("2024/2",  "202403/t20240328_3931768.htm"),
    ("2024/3",  "202404/t20240430_3933918.htm"),
    ("2024/4",  "202405/t20240531_3936271.htm"),
    ("2024/5",  "202406/t20240627_3938206.htm"),
    ("2024/6",  "202407/t20240731_3940804.htm"),
    ("2024/7",  "202408/t20240830_3942885.htm"),
    ("2024/8",  "202409/t20240930_3944792.htm"),
    ("2024/9",  "202410/t20241029_3946473.htm"),
    ("2024/10", "202411/t20241129_3948536.htm"),
    ("2024/11", "202412/t20241227_3950717.htm"),
    # 2025
    ("2025/1",  "202503/t20250328_3960903.htm"),
    ("2025/2",  "202503/t20250328_3960904.htm"),
    ("2025/3",  "202504/t20250428_3962945.htm"),
    ("2025/4",  "202505/t20250528_3964717.htm"),
    ("2025/5",  "202506/t20250627_3966682.htm"),
    ("2025/6",  "202507/t20250730_3968958.htm"),
    ("2025/7",  "202508/t20250828_3970990.htm"),
    ("2025/8",  "202509/t20250929_3973481.htm"),
    ("2025/9",  "202510/t20251024_3974884.htm"),
]


def fetch_page(url, max_retries=10):
    """Fetch a page with retries for 502 errors."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                resp.encoding = 'utf-8'
                return resp.text
            elif resp.status_code == 502:
                wait = 3 + attempt * 2
                print(f"  502 error, retry {attempt+1}/{max_retries} in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  HTTP {resp.status_code}, retry {attempt+1}/{max_retries}...")
                time.sleep(3)
        except Exception as e:
            print(f"  Error: {e}, retry {attempt+1}/{max_retries}...")
            time.sleep(3)
    return None


def num(text):
    """Extract a number from text like '8761' or '3.35' etc."""
    if not text:
        return None
    text = text.replace(",", "").replace("，", "").replace(" ", "").replace("\xa0", "")
    m = re.search(r'([\d]+\.?\d*)', text)
    if m:
        return float(m.group(1))
    return None


def find_num(pattern, text):
    """Search for pattern in text and return the first captured group as number."""
    m = re.search(pattern, text)
    if m:
        return num(m.group(1))
    return None


def find_two_nums(pattern, text):
    """Search for pattern in text and return two captured groups as numbers."""
    m = re.search(pattern, text)
    if m:
        return num(m.group(1)), num(m.group(2))
    return None, None


def extract_text(html):
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    content_div = (
        soup.find("div", class_="TRS_Editor")
        or soup.find("div", class_="my_doccontent")
        or soup.find("div", class_="content")
        or soup.find("div", id="zoom")
    )
    if not content_div:
        text = soup.get_text()
    else:
        text = content_div.get_text()
    # Normalize whitespace but keep structure
    text = re.sub(r'[\t ]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()


def split_monthly_ytd(text, year, month):
    """Split text into monthly section and YTD section."""
    if month == 1:
        return text, text

    # Look for section headers that mark the YTD part
    # e.g. "（二）1-9月发行情况" or "2025年1-9月"
    patterns = [
        rf'[（(]二[）)]\s*1\s*[-—]\s*{month}\s*月',
        rf'{year}年1\s*[-—]\s*{month}\s*月',
        rf'1\s*[-—]\s*{month}\s*月发行情况',
    ]
    split_pos = None
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            split_pos = m.start()
            break

    if split_pos is None:
        # Try a more general approach
        m = re.search(rf'1[-—]{month}月', text)
        if m:
            split_pos = m.start()

    if split_pos and split_pos > 50:
        return text[:split_pos], text[split_pos:]
    else:
        return text, text


def parse_report(html, period):
    """Parse a single report page and extract all required data."""
    text = extract_text(html)

    data = {"period": period}
    year = int(period.split("/")[0])
    month = int(period.split("/")[1])

    monthly_text, ytd_text = split_monthly_ytd(text, year, month)

    # ===== MONTHLY SECTION =====

    # --- Monthly new bonds ---
    # Pattern: "发行新增债券4741亿元，其中一般债券550亿元、专项债券4191亿元"
    # or: "全国发行新增债券4741亿元"
    data["monthly_new_total"] = find_num(
        r'发行新增债券\s*([\d,.]+)\s*亿元', monthly_text)

    g, s = find_two_nums(
        r'发行新增债券\s*[\d,.]+\s*亿元[，,]\s*其中[，,]?\s*一般债券\s*([\d,.]+)\s*亿元[、，,]\s*专项债券\s*([\d,.]+)\s*亿元',
        monthly_text)
    data["monthly_new_general"] = g
    data["monthly_new_special"] = s

    # --- Monthly refinancing bonds ---
    data["monthly_refi_total"] = find_num(
        r'发行再融资债券\s*([\d,.]+)\s*亿元', monthly_text)

    g, s = find_two_nums(
        r'发行再融资债券\s*[\d,.]+\s*亿元[，,]\s*其中[，,]?\s*一般债券\s*([\d,.]+)\s*亿元[、，,]\s*专项债券\s*([\d,.]+)\s*亿元',
        monthly_text)
    data["monthly_refi_general"] = g
    data["monthly_refi_special"] = s

    # --- Monthly total issuance ---
    # "合计，全国发行地方政府债券8619亿元"
    # or "全国发行地方政府债券8619亿元" in monthly section
    data["monthly_total"] = find_num(
        r'合计[，,]?\s*全国发行地方政府债券\s*([\d,.]+)\s*亿元', monthly_text)
    if data["monthly_total"] is None:
        # Try pattern without 合计: "X月，全国发行地方政府债券XXXX亿元"
        data["monthly_total"] = find_num(
            rf'{month}月[，,]\s*全国发行地方政府债券\s*([\d,.]+)\s*亿元', monthly_text)
    if data["monthly_total"] is None:
        # Compute from new + refi
        if data["monthly_new_total"] is not None and data["monthly_refi_total"] is not None:
            data["monthly_total"] = data["monthly_new_total"] + data["monthly_refi_total"]

    # --- Monthly average term ---
    data["monthly_avg_term"] = find_num(
        r'地方政府债券平均发行期限\s*([\d.]+)\s*年', monthly_text)
    if data["monthly_avg_term"] is None:
        data["monthly_avg_term"] = find_num(
            r'平均发行期限\s*([\d.]+)\s*年', monthly_text)

    # --- Monthly average rate ---
    data["monthly_avg_rate"] = find_num(
        r'地方政府债券平均发行利率\s*([\d.]+)\s*%', monthly_text)
    if data["monthly_avg_rate"] is None:
        data["monthly_avg_rate"] = find_num(
            r'平均发行利率\s*([\d.]+)\s*%', monthly_text)

    # ===== YTD SECTION =====

    if month == 1:
        # January: YTD = monthly
        for key in ["total", "new_total", "new_general", "new_special",
                     "refi_total", "refi_general", "refi_special",
                     "avg_term", "avg_rate"]:
            data[f"ytd_{key}"] = data[f"monthly_{key}"]
    else:
        # YTD new bonds
        # "全国发行新增地方政府债券43615亿元" or "发行新增债券43615亿元"
        data["ytd_new_total"] = find_num(
            r'发行新增(?:地方政府)?债券\s*([\d,.]+)\s*亿元', ytd_text)

        g, s = find_two_nums(
            r'发行新增(?:地方政府)?债券\s*[\d,.]+\s*亿元[，,]\s*其中[，,]?\s*一般债券\s*([\d,.]+)\s*亿元[、，,]\s*专项债券\s*([\d,.]+)\s*亿元',
            ytd_text)
        data["ytd_new_general"] = g
        data["ytd_new_special"] = s

        # YTD refinancing
        data["ytd_refi_total"] = find_num(
            r'发行再融资债券\s*([\d,.]+)\s*亿元', ytd_text)

        g, s = find_two_nums(
            r'发行再融资债券\s*[\d,.]+\s*亿元[，,]\s*其中[，,]?\s*一般债券\s*([\d,.]+)\s*亿元[、，,]\s*专项债券\s*([\d,.]+)\s*亿元',
            ytd_text)
        data["ytd_refi_general"] = g
        data["ytd_refi_special"] = s

        # YTD total
        # "全国发行地方政府债券合计85457亿元" or "全国发行地方政府债券XXXXX亿元"
        data["ytd_total"] = find_num(
            r'发行地方政府债券合计\s*([\d,.]+)\s*亿元', ytd_text)
        if data["ytd_total"] is None:
            data["ytd_total"] = find_num(
                r'全国发行地方政府债券\s*([\d,.]+)\s*亿元', ytd_text)
        if data["ytd_total"] is None and data["ytd_new_total"] and data["ytd_refi_total"]:
            data["ytd_total"] = data["ytd_new_total"] + data["ytd_refi_total"]

        # YTD average term
        data["ytd_avg_term"] = find_num(
            r'平均发行期限\s*([\d.]+)\s*年', ytd_text)

        # YTD average rate
        data["ytd_avg_rate"] = find_num(
            r'平均发行利率\s*([\d.]+)\s*%', ytd_text)

    # ===== DEBT SECTION (from full text) =====

    # Debt limit
    # "地方政府债务限额为579874.3亿元" or "地方政府债务限额579874.3亿元"
    data["debt_limit_total"] = find_num(
        r'地方政府债务限额[为]?\s*([\d,.]+)\s*亿元', text)
    data["debt_limit_general"] = find_num(
        r'一般债务限额[为]?\s*([\d,.]+)\s*亿元', text)
    data["debt_limit_special"] = find_num(
        r'专项债务限额[为]?\s*([\d,.]+)\s*亿元', text)

    # Debt balance - look in the balance section specifically
    # "全国地方政府债务余额536995亿元"
    data["debt_balance_total"] = find_num(
        r'地方政府债务余额\s*([\d,.]+)\s*亿元', text)

    # General/special balance from the balance section
    # "其中，一般债务173119亿元，专项债务363876亿元"
    # Find section after 债务余额
    balance_pos = text.find('债务余额情况')
    if balance_pos == -1:
        balance_pos = text.find('债务余额')
    if balance_pos >= 0:
        balance_text = text[balance_pos:]
    else:
        balance_text = text

    data["debt_balance_general"] = find_num(
        r'一般债务\s*([\d,.]+)\s*亿元', balance_text)
    data["debt_balance_special"] = find_num(
        r'专项债务\s*([\d,.]+)\s*亿元', balance_text)

    return data


def main():
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "csv_import", "中国地方政府債券発行・債務残高.csv"
    )

    all_data = []
    failed = []

    for period, path in REPORTS:
        url = BASE_URL + path
        print(f"Fetching {period}: {url}")

        html = fetch_page(url)
        if not html:
            print(f"  FAILED to fetch {period} after all retries")
            failed.append(period)
            continue

        try:
            data = parse_report(html, period)
            all_data.append(data)

            mt = data.get("monthly_total", "?")
            mr = data.get("monthly_avg_rate", "?")
            bl = data.get("debt_balance_total", "?")
            print(f"  OK: total={mt}, rate={mr}%, balance={bl}")
        except Exception as e:
            print(f"  PARSE ERROR for {period}: {e}")
            import traceback
            traceback.print_exc()
            failed.append(period)

        # Be polite to the server
        time.sleep(1.5)

    if failed:
        print(f"\nFailed periods: {failed}")

    # Write CSV
    fields = [
        "period",
        "monthly_total",
        "monthly_new_total", "monthly_new_general", "monthly_new_special",
        "monthly_refi_total", "monthly_refi_general", "monthly_refi_special",
        "monthly_avg_term", "monthly_avg_rate",
        "ytd_total",
        "ytd_new_total", "ytd_new_general", "ytd_new_special",
        "ytd_refi_total", "ytd_refi_general", "ytd_refi_special",
        "ytd_avg_term", "ytd_avg_rate",
        "debt_limit_total", "debt_limit_general", "debt_limit_special",
        "debt_balance_total", "debt_balance_general", "debt_balance_special",
    ]

    headers = [
        "公表月",
        "当月総発行額(億元)",
        "当月新増合計(億元)", "当月新増一般(億元)", "当月新増専項(億元)",
        "当月再融資合計(億元)", "当月再融資一般(億元)", "当月再融資専項(億元)",
        "当月平均発行期限(年)", "当月平均発行利率(%)",
        "年初来総発行額(億元)",
        "年初来新増合計(億元)", "年初来新増一般(億元)", "年初来新増専項(億元)",
        "年初来再融資合計(億元)", "年初来再融資一般(億元)", "年初来再融資専項(億元)",
        "年初来平均発行期限(年)", "年初来平均発行利率(%)",
        "債務限額合計(億元)", "債務限額一般(億元)", "債務限額専項(億元)",
        "債務残高合計(億元)", "債務残高一般(億元)", "債務残高専項(億元)",
    ]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in all_data:
            csv_row = []
            for field in fields:
                val = row.get(field, "")
                if val is None:
                    csv_row.append("")
                elif isinstance(val, float) and val == int(val):
                    csv_row.append(str(int(val)))
                else:
                    csv_row.append(str(val))
            writer.writerow(csv_row)

    print(f"\nCSV written to {output_path} ({len(all_data)} rows)")

    # Data completeness check
    print("\n--- Data completeness check ---")
    for row in all_data:
        missing = [k for k, v in row.items() if v is None and k != "period"
                   and not k.startswith("debt_limit")]  # limit may genuinely be missing
        if missing:
            print(f"  {row['period']}: missing {missing}")


if __name__ == "__main__":
    main()
