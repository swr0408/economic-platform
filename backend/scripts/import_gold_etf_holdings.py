"""
金ETF保有残高 歴史データインポートスクリプト

SPDR Gold Shares API からExcelをダウンロードし、
yfinance GC=F の金価格とマージしてDBに格納する。

Usage:
    cd backend
    python scripts/import_gold_etf_holdings.py
"""
import io
import re
import sys
import logging
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import requests
import yfinance as yf

sys.path.insert(0, ".")
from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

SPDR_API_URL = (
    "https://api.spdrgoldshares.com/api/v1/historical-archive"
    "?product=1326&exchange=TSE&lang=ja"
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
SHEET_NAME = "JP 1326 Historical Archive"


def _find_column(df: pd.DataFrame, patterns: list[str]) -> str:
    """列名を正規表現パターンで検索"""
    for pat in patterns:
        rgx = re.compile(pat, re.I)
        for col in df.columns:
            if rgx.search(str(col)):
                return col
    raise ValueError(f"Column not found: {patterns}")


def _parse_numeric(series: pd.Series) -> pd.Series:
    """カンマ・全角マイナス対応の数値パース"""
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("\u2212", "-", regex=False)  # 全角マイナス
        .str.replace("\u2013", "-", regex=False)   # en-dash
        .str.strip(),
        errors="coerce",
    )


def download_and_parse_spdr() -> pd.DataFrame:
    """SPDR API からExcelをダウンロードしパース"""
    logger.info(f"Downloading SPDR Excel from API...")
    resp = requests.get(SPDR_API_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    logger.info(f"Downloaded {len(resp.content)} bytes")

    # ヘッダー行自動検出
    tmp = pd.read_excel(
        io.BytesIO(resp.content), sheet_name=SHEET_NAME, header=None, engine="openpyxl"
    )
    header_row = tmp[
        tmp.iloc[:, 0].astype(str).str.contains(r"^(?:Date|日付)$", case=False, na=False)
    ].index[0]
    logger.info(f"Header row: {header_row}")

    df = pd.read_excel(
        io.BytesIO(resp.content),
        sheet_name=SHEET_NAME,
        header=header_row,
        engine="openpyxl",
    )
    # 列名正規化
    df.columns = (
        df.columns.astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.replace("\u3000", " ")
        .str.strip()
    )
    logger.info(f"Columns: {df.columns.tolist()}")

    # 休業日行を除外
    first_col = df.columns[0]
    mask = df[first_col].astype(str).str.contains("Holiday|休場|休業", na=False)
    df = df[~mask].copy()
    logger.info(f"Rows after holiday removal: {len(df)}")

    # 列を検索
    date_col = _find_column(df, [r"^日付$", r"^Date$"])
    ton_col = _find_column(df, [r"金保有量.*トン", r"ton"])
    nav_col = _find_column(df, [r"信託総純資産額", r"Net Asset Value"])
    close_usd_col = _find_column(df, [r"1326.*終値.*ドル", r"1326.*Close.*USD"])
    close_jpy_col = _find_column(df, [r"1326.*終値.*円", r"1326.*Close.*JPY"])

    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    result["holdings_ton"] = _parse_numeric(df[ton_col])
    result["nav_usd"] = _parse_numeric(df[nav_col])
    result["close_usd"] = _parse_numeric(df[close_usd_col])
    result["close_jpy"] = _parse_numeric(df[close_jpy_col])

    result = result[result["date"].notna()].sort_values("date").reset_index(drop=True)
    logger.info(f"Parsed {len(result)} records ({result['date'].min()} ~ {result['date'].max()})")
    return result


def fetch_gold_price(start_date: str) -> dict[str, float]:
    """yfinance GC=F から金価格を取得"""
    logger.info(f"Fetching gold price (GC=F) from {start_date}...")
    ticker = yf.Ticker("GC=F")
    hist = ticker.history(start=start_date, interval="1d")
    if hist.empty:
        logger.warning("No gold price data from yfinance")
        return {}

    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    price_map = {}
    for idx, row in hist.iterrows():
        price_map[idx.strftime("%Y-%m-%d")] = round(float(row["Close"]), 2)
    logger.info(f"Gold price: {len(price_map)} days")
    return price_map


def import_to_db(etf_df: pd.DataFrame, gold_map: dict[str, float]) -> int:
    """DBにUPSERT"""
    count = 0
    with SessionLocal() as session:
        for _, row in etf_df.iterrows():
            date_str = row["date"].strftime("%Y-%m-%d")
            gold_price = gold_map.get(date_str)

            session.execute(
                text("""
                    INSERT INTO gold_etf_holdings
                        (date, holdings_ton, nav_usd, close_usd, close_jpy, gold_price_usd, source)
                    VALUES
                        (:date, :holdings_ton, :nav_usd, :close_usd, :close_jpy, :gold_price_usd, 'SPDR')
                    ON CONFLICT (date) DO UPDATE SET
                        holdings_ton = EXCLUDED.holdings_ton,
                        nav_usd = EXCLUDED.nav_usd,
                        close_usd = EXCLUDED.close_usd,
                        close_jpy = EXCLUDED.close_jpy,
                        gold_price_usd = COALESCE(EXCLUDED.gold_price_usd, gold_etf_holdings.gold_price_usd),
                        updated_at = NOW()
                """),
                {
                    "date": date_str,
                    "holdings_ton": None if pd.isna(row["holdings_ton"]) else float(row["holdings_ton"]),
                    "nav_usd": None if pd.isna(row["nav_usd"]) else float(row["nav_usd"]),
                    "close_usd": None if pd.isna(row["close_usd"]) else float(row["close_usd"]),
                    "close_jpy": None if pd.isna(row["close_jpy"]) else float(row["close_jpy"]),
                    "gold_price_usd": gold_price,
                },
            )
            count += 1

        session.commit()

    return count


def main():
    # 1. SPDR Excel
    etf_df = download_and_parse_spdr()

    # 2. yfinance gold price
    start_date = etf_df["date"].min().strftime("%Y-%m-%d")
    gold_map = fetch_gold_price(start_date)

    # 3. DB import
    count = import_to_db(etf_df, gold_map)
    logger.info(f"Imported {count} records to gold_etf_holdings")

    # 4. Verify
    with SessionLocal() as session:
        result = session.execute(text("SELECT COUNT(*) FROM gold_etf_holdings")).fetchone()
        logger.info(f"Total records in DB: {result[0]}")
        latest = session.execute(
            text("SELECT date, holdings_ton, gold_price_usd FROM gold_etf_holdings ORDER BY date DESC LIMIT 3")
        ).fetchall()
        for r in latest:
            logger.info(f"  {r[0]}: holdings={r[1]} ton, gold=${r[2]}")


if __name__ == "__main__":
    main()
