"""
JPX 指数オプション Put/Call Ratio 月次ファイルインポート

SIOP_D_{yyyymm}.xlsx の BO_DM0032 シートから日次データを抽出し、
jpx_put_call_ratio テーブルに保存する。

データ利用可能期間: 2020/01～
"""
import sys
import os
import io
import time
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

import requests
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

SIOP_URL = "https://www.jpx.co.jp/automation/markets/statistics-derivatives/monthly-statistics/files/{yyyy}/SIOP_D_{yyyymm}.xlsx"

# 2020-2023のアーカイブURL（ランダムハッシュ含むため固定）
ARCHIVE_URLS = {
    "202001": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000004jjmv-att/SIOP_D_202001.xlsx",
    "202002": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000004ltkw-att/SIOP_D_202002.xlsx",
    "202003": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000004nvq2-att/SIOP_D_202003.xlsx",
    "202004": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000004q179-att/SIOP_D_202004.xlsx",
    "202005": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000004rfbr-att/SIOP_D_202005.xlsx",
    "202006": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000004trhq-att/SIOP_D_202006.xlsx",
    "202007": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000004vz2s-att/SIOP_D_202007.xlsx",
    "202008": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000004xk35-att/SIOP_D_202008.xlsx",
    "202009": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu0000050uxq-att/SIOP_D_202009.xlsx",
    "202010": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu0000052zys-att/SIOP_D_202010.xlsx",
    "202011": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu0000055gj2-att/SIOP_D_202011.xlsx",
    "202012": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu0000058brp-att/SIOP_D_202012.xlsx",
    "202101": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005ad2y-att/SIOP_D_202101.xlsx",
    "202102": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005cx50-att/SIOP_D_202102.xlsx",
    "202103": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005hqyp-att/SIOP_D_202103.xlsx",
    "202104": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005jjsz-att/SIOP_D_202104.xlsx",
    "202105": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005l77m-att/SIOP_D_202105.xlsx",
    "202106": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005nr20-att/SIOP_D_202106.xlsx",
    "202107": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005pxip-att/SIOP_D_202107.xlsx",
    "202108": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005rynp-att/SIOP_D_202108.xlsx",
    "202109": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005vc5e-att/SIOP_D_202109.xlsx",
    "202110": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000005zchj-att/SIOP_D_202110.xlsx",
    "202111": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu0000061u4j-att/SIOP_D_202111.xlsx",
    "202112": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu0000063wqz-att/SIOP_D_202112.xlsx",
    "202201": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu0000065otz-att/SIOP_D_202201.xlsx",
    "202202": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu0000067wqs-att/SIOP_D_202202.xlsx",
    "202203": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000006b9az-att/SIOP_D_202203.xlsx",
    "202204": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000006e7ql-att/SIOP_D_202204.xlsx",
    "202205": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000006fz9s-att/SIOP_D_202205.xlsx",
    "202206": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000006i7sz-att/SIOP_D_202206.xlsx",
    "202207": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000006k2ht-att/SIOP_D_202207.xlsx",
    "202208": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000006m0ho-att/SIOP_D_202208.xlsx",
    "202209": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/nlsgeu000006o8m8-att/SIOP_D_202209.xlsx",
    "202210": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/co3pgt000000139f-att/SIOP_D_202210.xlsx",
    "202211": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/co3pgt0000003cjb-att/SIOP_D_202211.xlsx",
    "202212": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/co3pgt0000005d1f-att/SIOP_D_202212.xlsx",
    "202301": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/fi1l5r0000001l81-att/SIOP_D_202301.xlsx",
    "202302": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/cg27su000000285r-att/SIOP_D_202302.xlsx",
    "202303": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/cg27su0000004hzt-att/SIOP_D_202303.xlsx",
    "202304": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/cg27su0000006gpi-att/SIOP_D_202304.xlsx",
    "202305": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/cg27su0000008yuy-att/SIOP_D_202305.xlsx",
    "202306": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/aocfb40000001xgl-att/SIOP_D_202306.xlsx",
    "202307": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/aocfb40000003v7b-att/SIOP_D_202307.xlsx",
    "202308": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/jr4eth0000001li7-att/SIOP_D_202308.xlsx",
    "202309": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/jr4eth0000003o6z-att/SIOP_D_202309.xlsx",
    "202310": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/bkk2ed0000001ckx-att/SIOP_D_202310.xlsx",
    "202311": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/bkk2ed0000003mgr-att/SIOP_D_202311.xlsx",
    "202312": "https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/bkk2ed0000005v7v-att/SIOP_D_202312.xlsx",
}

# Product name → DB product key
PRODUCT_MAP = {
    "Nikkei 225 Options": "nikkei225",
    "Nikkei 225 mini Options": "nikkei225_mini",
    "TOPIX Options": "topix",
}

# Column indices (0-based) in BO_DM0032
COL_DATE = 0       # A: Date
COL_PRODUCT_EN = 2 # C: English product name
COL_PUT_VOL = 4    # E: Put Trading Volume
COL_CALL_VOL = 6   # G: Call Trading Volume
COL_PUT_OI = 25    # Z: Put Open Interest
COL_CALL_OI = 27   # AB: Call Open Interest


def download_siop_file(year: int, month: int) -> Optional[bytes]:
    """SIOP月次ファイルをダウンロード（2020-2023はアーカイブURL、2024+はautomation URL）"""
    yyyymm = f"{year:04d}{month:02d}"

    # アーカイブURL優先（2020-2023）
    if yyyymm in ARCHIVE_URLS:
        url = ARCHIVE_URLS[yyyymm]
    else:
        url = SIOP_URL.format(yyyy=str(year), yyyymm=yyyymm)

    logger.info(f"Downloading: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 200:
            logger.info(f"  Downloaded {len(resp.content)} bytes")
            return resp.content
        else:
            logger.warning(f"  HTTP {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"  Download error: {e}")
        return None


def parse_siop_sheet(content: bytes, year: int, month: int) -> List[Dict]:
    """BO_DM0032シートからデータを抽出"""
    df = pd.read_excel(io.BytesIO(content), sheet_name="BO_DM0032", header=None)
    rows = df.shape[0]

    results = []
    current_product = None
    current_month_start = None  # The first date value tells us the month.day format

    for row_idx in range(9, rows):  # Data starts at row 10 (0-based: 9)
        # Check column C for product name
        product_val = df.iloc[row_idx, COL_PRODUCT_EN]
        if pd.notna(product_val) and isinstance(product_val, str):
            product_str = product_val.strip()
            if product_str in PRODUCT_MAP:
                current_product = PRODUCT_MAP[product_str]
            elif product_str and product_str not in ("", "Products"):
                # Different product, skip
                current_product = None

        if current_product is None:
            continue

        # Parse date from column A
        date_val = df.iloc[row_idx, COL_DATE]
        if pd.isna(date_val):
            continue

        day = None
        date_str_raw = str(date_val).strip()

        # Format: "M.D" for first row, or just "D" for subsequent rows
        if "." in date_str_raw:
            try:
                parts = date_str_raw.split(".")
                m = int(float(parts[0]))
                d = int(float(parts[1]))
                if m == month:
                    day = d
            except (ValueError, IndexError):
                continue
        else:
            try:
                day = int(float(date_str_raw))
            except (ValueError, TypeError):
                continue

        if day is None or day < 1 or day > 31:
            continue

        try:
            dt = date(year, month, day)
        except ValueError:
            continue

        # Read values
        put_vol = df.iloc[row_idx, COL_PUT_VOL]
        call_vol = df.iloc[row_idx, COL_CALL_VOL]
        put_oi = df.iloc[row_idx, COL_PUT_OI]
        call_oi = df.iloc[row_idx, COL_CALL_OI]

        # Skip non-trading days (all None)
        if pd.isna(put_vol) and pd.isna(call_vol):
            continue

        def safe_int(v):
            if pd.isna(v):
                return None
            try:
                return int(v)
            except (ValueError, TypeError):
                return None

        put_vol_int = safe_int(put_vol) or 0
        call_vol_int = safe_int(call_vol) or 0
        put_oi_int = safe_int(put_oi)
        call_oi_int = safe_int(call_oi)

        # Calculate PCR
        volume_pcr = round(put_vol_int / call_vol_int, 4) if call_vol_int > 0 else None
        oi_pcr = None
        if put_oi_int is not None and call_oi_int is not None and call_oi_int > 0:
            oi_pcr = round(put_oi_int / call_oi_int, 4)

        results.append({
            "date": dt.strftime("%Y-%m-%d"),
            "product": current_product,
            "put_volume": put_vol_int,
            "call_volume": call_vol_int,
            "put_oi": put_oi_int,
            "call_oi": call_oi_int,
            "volume_pcr": volume_pcr,
            "oi_pcr": oi_pcr,
        })

    return results


def import_to_db(records: List[Dict]) -> Tuple[int, int]:
    """DBにインポート"""
    inserted = 0
    errors = 0

    with SessionLocal() as session:
        # テーブル作成
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS jpx_put_call_ratio (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                product VARCHAR(30) NOT NULL,
                put_volume BIGINT,
                call_volume BIGINT,
                put_oi BIGINT,
                call_oi BIGINT,
                volume_pcr NUMERIC(10, 4),
                oi_pcr NUMERIC(10, 4),
                source VARCHAR(50) DEFAULT 'JPX',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                CONSTRAINT jpx_pcr_date_product_unique UNIQUE (date, product)
            )
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_jpx_pcr_date
            ON jpx_put_call_ratio (date DESC)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_jpx_pcr_product_date
            ON jpx_put_call_ratio (product, date DESC)
        """))
        session.commit()

        for rec in records:
            try:
                session.execute(text("""
                    INSERT INTO jpx_put_call_ratio
                        (date, product, put_volume, call_volume, put_oi, call_oi,
                         volume_pcr, oi_pcr, source)
                    VALUES
                        (:date, :product, :put_volume, :call_volume, :put_oi, :call_oi,
                         :volume_pcr, :oi_pcr, 'SIOP')
                    ON CONFLICT (date, product) DO UPDATE SET
                        put_volume = EXCLUDED.put_volume,
                        call_volume = EXCLUDED.call_volume,
                        put_oi = EXCLUDED.put_oi,
                        call_oi = EXCLUDED.call_oi,
                        volume_pcr = EXCLUDED.volume_pcr,
                        oi_pcr = EXCLUDED.oi_pcr,
                        source = 'SIOP',
                        updated_at = NOW()
                """), rec)
                inserted += 1
            except Exception as e:
                logger.error(f"  Insert error: {e}")
                errors += 1

        session.commit()

    return inserted, errors


def main():
    """2020/01～現在までの全SIOPファイルをインポート"""
    now = datetime.now()
    start_year = 2020
    start_month = 1

    total_inserted = 0
    total_errors = 0

    year = start_year
    month = start_month

    while (year < now.year) or (year == now.year and month <= now.month):
        content = download_siop_file(year, month)
        if content:
            records = parse_siop_sheet(content, year, month)
            if records:
                inserted, errors = import_to_db(records)
                total_inserted += inserted
                total_errors += errors
                logger.info(f"  {year}/{month:02d}: {inserted} records, {errors} errors")
            else:
                logger.warning(f"  {year}/{month:02d}: No records parsed")
        else:
            logger.warning(f"  {year}/{month:02d}: File not available")

        # Next month
        month += 1
        if month > 12:
            month = 1
            year += 1

        # Rate limiting
        time.sleep(1)

    logger.info(f"\nTotal: inserted={total_inserted}, errors={total_errors}")


if __name__ == "__main__":
    main()
