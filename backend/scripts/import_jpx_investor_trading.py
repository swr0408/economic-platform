"""
投資部門別売買状況 インポートスクリプト

データソース:
  1. ローカルXLSファイル: C:/Users/owner/Downloads/FX/nikkeibalance/stock_val_1_*.xlsx
  2. JPXウェブサイト: index.html から最新週次XLSをダウンロード

XLSファイル構造 (stock_val_1_YYMMWW.xls, sheet='Tokyo & Nagoya'):
  Row 3, Col 0: 日付情報 (例: '2024年1月第1週 2024/1 week1  ( 1/4 - 1/5 )')
  Row 12, Col 10: 自己計 (Proprietary) ネット売買金額
  Row 26, Col 10: 個人 (Individuals) ネット売買金額
  Row 30, Col 10: 海外投資家 (Foreigners) ネット売買金額
  Row 38, Col 10: 投資信託 (Investment Trusts) ネット売買金額
  Row 41, Col 10: 事業法人 (Business Corps) ネット売買金額
  Row 58, Col 10: 信託銀行 (Trust Banks) ネット売買金額
  単位: 千円, カンマ付き, 全角マイナス (−, U+2212) の場合あり

Usage:
  cd backend
  python scripts/import_jpx_investor_trading.py
  python scripts/import_jpx_investor_trading.py --web-only   # JPXウェブのみ
  python scripts/import_jpx_investor_trading.py --local-only  # ローカルのみ
"""
import io
import os
import re
import sys
import logging
import argparse
from glob import glob
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ローカルXLSファイルのディレクトリ
LOCAL_XLS_DIR = Path("C:/Users/owner/Downloads/FX/nikkeibalance")

# JPX base URL
JPX_BASE = "https://www.jpx.co.jp"
JPX_INDEX_URL = f"{JPX_BASE}/markets/statistics-equities/investor-type/index.html"

# XLS行位置マッピング (0-based pandas index)
# フォーマットが年によって異なるため、複数候補を試行
ROW_POSITIONS = {
    "proprietary": [12, 13],       # 自己計 / Proprietary
    "individuals": [26, 27],       # 個人 / Individuals
    "foreigners": [29, 30, 31],    # 海外投資家 / Foreigners
    "investment_trusts": [37, 38], # 投資信託 / Investment Trusts
    "business_corps": [41, 42],    # 事業法人 / Business Cos.
    "trust_banks": [57, 58],       # 信託銀行 / Trust BK
}
NET_COL = 10  # K列 = ネット売買金額


def _parse_value(val) -> int | None:
    """カンマ付き・全角マイナス対応の値パース"""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s == "-" or s == "−":
        return None
    # 全角マイナス → 半角
    s = s.replace("−", "-").replace("–", "-")
    # カンマ除去
    s = s.replace(",", "")
    # 引用符除去
    s = s.strip('"').strip("'")
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return None


def _parse_date_from_xls(df: pd.DataFrame) -> str | None:
    """XLSのRow 3, Col 0から日付を抽出"""
    raw = df.iloc[3, 0]
    if pd.isna(raw):
        return None
    raw = str(raw)

    # パターン: ( M/D - M/D ) から開始日を取得
    match_paren = re.search(r"\(\s*(\d+)/(\d+)\s*-\s*(\d+)/(\d+)\s*\)", raw)
    year_match = re.search(r"(\d{4})", raw)

    if match_paren and year_match:
        year = int(year_match.group(1))
        start_month = int(match_paren.group(1))
        start_day = int(match_paren.group(2))
        try:
            dt = datetime(year, start_month, start_day)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def _parse_xls(df: pd.DataFrame) -> dict | None:
    """XLS DataFrameから1週分のデータを抽出"""
    date_str = _parse_date_from_xls(df)
    if not date_str:
        return None

    record = {"date": date_str}
    for col_name, row_candidates in ROW_POSITIONS.items():
        found = None
        for row_idx in row_candidates:
            if row_idx >= df.shape[0] or NET_COL >= df.shape[1]:
                continue
            val = df.iloc[row_idx, NET_COL]
            parsed = _parse_value(val)
            if parsed is not None:
                found = parsed
                break
        record[col_name] = found

    return record


def import_from_local():
    """ローカルXLSファイルからインポート"""
    pattern = str(LOCAL_XLS_DIR / "stock_val_1_*.xlsx")
    files = sorted(glob(pattern))
    logger.info(f"Found {len(files)} local XLS files")

    records = []
    for fpath in files:
        try:
            df = pd.read_excel(fpath, sheet_name="Tokyo & Nagoya", header=None)
            rec = _parse_xls(df)
            if rec:
                records.append(rec)
            else:
                logger.warning(f"Failed to parse: {fpath}")
        except Exception as e:
            logger.warning(f"Error reading {fpath}: {e}")

    logger.info(f"Parsed {len(records)} records from local files")
    return records


def _scrape_xls_urls_from_page(page_url: str) -> list[str]:
    """ページからweekly XLS URLを抽出"""
    from bs4 import BeautifulSoup

    resp = requests.get(page_url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        logger.warning(f"HTTP {resp.status_code}: {page_url}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    xls_urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "stock_val_1_" in href and href.endswith(".xls"):
            fname = href.split("/")[-1]
            # monthly/yearlyを除外
            if "_m" not in fname and "_y" not in fname:
                full_url = JPX_BASE + href if href.startswith("/") else href
                xls_urls.append(full_url)
    return xls_urls


def _download_and_parse(xls_urls: list[str]) -> list[dict]:
    """XLS URLリストをダウンロード・パースしてレコード一覧を返す"""
    records = []
    for url in xls_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"HTTP {resp.status_code}: {url}")
                continue

            df = pd.read_excel(io.BytesIO(resp.content), sheet_name="Tokyo & Nagoya", header=None)
            rec = _parse_xls(df)
            if rec:
                records.append(rec)
            else:
                logger.warning(f"  Failed to parse: {url}")
        except Exception as e:
            logger.warning(f"  Error: {url}: {e}")
    return records


def import_from_web():
    """JPXウェブサイト（最新ページのみ）からXLSをダウンロードしてインポート"""
    logger.info(f"Fetching JPX index page: {JPX_INDEX_URL}")
    xls_urls = _scrape_xls_urls_from_page(JPX_INDEX_URL)
    logger.info(f"Found {len(xls_urls)} weekly XLS links on JPX index")
    records = _download_and_parse(xls_urls)
    logger.info(f"Parsed {len(records)} records from JPX web")
    return records


def import_from_archives(start_year: int = 2016, end_year: int = 2025):
    """JPXアーカイブページ（2016〜2025）からXLSをダウンロードしてインポート

    アーカイブURL:
      2026 → 00-00-archives-00.html
      2025 → 00-00-archives-01.html
      ...
      2016 → 00-00-archives-10.html
    """
    from bs4 import BeautifulSoup

    all_records = []
    for year in range(start_year, end_year + 1):
        archive_idx = 2026 - year
        archive_url = f"{JPX_BASE}/markets/statistics-equities/investor-type/00-00-archives-{archive_idx:02d}.html"
        logger.info(f"Fetching {year} archive: {archive_url}")

        xls_urls = _scrape_xls_urls_from_page(archive_url)
        logger.info(f"  Found {len(xls_urls)} weekly XLS links for {year}")

        if not xls_urls:
            logger.warning(f"  No weekly XLS found for {year}, skipping")
            continue

        records = _download_and_parse(xls_urls)
        all_records.extend(records)
        logger.info(f"  Parsed {len(records)} records for {year}")

    logger.info(f"Total parsed from archives: {len(all_records)} records")
    return all_records


def save_to_db(records: list[dict]):
    """レコードをDBに保存 (UPSERT)"""
    if not records:
        logger.info("No records to save")
        return

    with SessionLocal() as session:
        inserted = 0
        updated = 0
        for rec in records:
            result = session.execute(
                text("""
                    INSERT INTO jpx_investor_trading
                        (date, individuals, foreigners, trust_banks,
                         investment_trusts, business_corps, proprietary, source)
                    VALUES
                        (:date, :individuals, :foreigners, :trust_banks,
                         :investment_trusts, :business_corps, :proprietary, 'XLS')
                    ON CONFLICT (date) DO UPDATE SET
                        individuals = EXCLUDED.individuals,
                        foreigners = EXCLUDED.foreigners,
                        trust_banks = EXCLUDED.trust_banks,
                        investment_trusts = EXCLUDED.investment_trusts,
                        business_corps = EXCLUDED.business_corps,
                        proprietary = EXCLUDED.proprietary,
                        updated_at = NOW()
                """),
                rec,
            )
            if result.rowcount > 0:
                inserted += 1

        session.commit()

    logger.info(f"Saved {inserted} records to DB (upsert)")

    # Show date range
    dates = sorted([r["date"] for r in records])
    logger.info(f"Date range: {dates[0]} ~ {dates[-1]}")


def main():
    parser = argparse.ArgumentParser(description="Import JPX investor trading data")
    parser.add_argument("--local-only", action="store_true", help="Import from local XLS files only")
    parser.add_argument("--web-only", action="store_true", help="Import from JPX web only")
    parser.add_argument("--archives", action="store_true", help="Import from JPX archive pages (2016-2025)")
    parser.add_argument("--archives-year", type=int, help="Import specific year from archives (e.g. 2020)")
    args = parser.parse_args()

    all_records = []

    if args.archives or args.archives_year:
        # アーカイブモード
        if args.archives_year:
            archive_records = import_from_archives(args.archives_year, args.archives_year)
        else:
            archive_records = import_from_archives(2016, 2025)
        all_records.extend(archive_records)

        # 最新ページも取得
        web_records = import_from_web()
        all_records.extend(web_records)
    else:
        if not args.web_only:
            local_records = import_from_local()
            all_records.extend(local_records)

        if not args.local_only:
            web_records = import_from_web()
            all_records.extend(web_records)

    # 日付で重複除去（後のレコードが優先）
    by_date = {}
    for rec in all_records:
        by_date[rec["date"]] = rec
    unique_records = sorted(by_date.values(), key=lambda x: x["date"])

    logger.info(f"Total unique records: {len(unique_records)}")
    save_to_db(unique_records)


if __name__ == "__main__":
    main()
