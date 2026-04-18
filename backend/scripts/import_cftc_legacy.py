"""
CFTC Legacy COT (Futures Only) データインポート
CFTC API から Legacy Futures Only レポートをダウンロードし、金融19銘柄のNon-Commercial/Commercial をDBへ格納

※ コモディティ6銘柄は DisAgg テーブルから Legacy 相当値を算出するため、このスクリプトでは金融銘柄のみ対象
"""

import sys
import os
import io
import logging
import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LEGACY_API_URL = "https://publicreporting.cftc.gov/api/views/6dca-aqww/rows.csv?accessType=DOWNLOAD"

# Legacy COT で使用する CFTC Contract Market Code → asset_name
# 金融先物のコード（Legacy と TFF で同じ contract code を使用）
LEGACY_ASSETS = {
    "232741": "audusd",
    "099741": "eurusd",
    "096742": "gbpusd",
    "112741": "nzdusd",
    "090741": "usdcad",
    "092741": "usdchf",
    "097741": "usdjpy",
    "098662": "usd_index",
    "13874+": "sp500",
    "12460+": "dow",
    "20974+": "nasdaq100",
    "239742": "russell2000",
    "240743": "nikkei225",
    "042601": "us02y",
    "043602": "us10y",
    "020601": "us30y",
    "1170E1": "vix",
    "399741": "eurjpy",
    "299741": "eurgbp",
}

UPSERT_SQL = text("""
    INSERT INTO cftc_legacy_positions (
        date, asset_code, asset_name, open_interest,
        noncomm_long, noncomm_short, noncomm_spread, noncomm_net,
        comm_long, comm_short, comm_net,
        nonrept_long, nonrept_short, nonrept_net,
        source
    ) VALUES (
        :date, :asset_code, :asset_name, :open_interest,
        :noncomm_long, :noncomm_short, :noncomm_spread, :noncomm_net,
        :comm_long, :comm_short, :comm_net,
        :nonrept_long, :nonrept_short, :nonrept_net,
        'CFTC'
    )
    ON CONFLICT (date, asset_code) DO UPDATE SET
        asset_name = EXCLUDED.asset_name,
        open_interest = COALESCE(EXCLUDED.open_interest, cftc_legacy_positions.open_interest),
        noncomm_long = COALESCE(EXCLUDED.noncomm_long, cftc_legacy_positions.noncomm_long),
        noncomm_short = COALESCE(EXCLUDED.noncomm_short, cftc_legacy_positions.noncomm_short),
        noncomm_spread = COALESCE(EXCLUDED.noncomm_spread, cftc_legacy_positions.noncomm_spread),
        noncomm_net = COALESCE(EXCLUDED.noncomm_net, cftc_legacy_positions.noncomm_net),
        comm_long = COALESCE(EXCLUDED.comm_long, cftc_legacy_positions.comm_long),
        comm_short = COALESCE(EXCLUDED.comm_short, cftc_legacy_positions.comm_short),
        comm_net = COALESCE(EXCLUDED.comm_net, cftc_legacy_positions.comm_net),
        nonrept_long = COALESCE(EXCLUDED.nonrept_long, cftc_legacy_positions.nonrept_long),
        nonrept_short = COALESCE(EXCLUDED.nonrept_short, cftc_legacy_positions.nonrept_short),
        nonrept_net = COALESCE(EXCLUDED.nonrept_net, cftc_legacy_positions.nonrept_net),
        updated_at = NOW()
""")


def safe_float(val):
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def download_legacy_data() -> pd.DataFrame:
    """Download full Legacy Futures Only dataset from CFTC API."""
    logger.info(f"Downloading Legacy Futures Only data from {LEGACY_API_URL} ...")
    resp = requests.get(LEGACY_API_URL, timeout=600)
    resp.raise_for_status()
    logger.info(f"  Downloaded {len(resp.content) / 1024 / 1024:.1f} MB")

    df = pd.read_csv(io.StringIO(resp.text))
    logger.info(f"  Total rows: {len(df)}, Columns: {len(df.columns)}")
    # Print column names for debugging
    logger.info(f"  Column names: {list(df.columns[:30])}")
    return df


def main():
    df = download_legacy_data()

    # Normalize code column
    df["CFTC_Contract_Market_Code"] = df["CFTC_Contract_Market_Code"].astype(str).str.strip()

    # Filter target financial assets
    df_filtered = df[df["CFTC_Contract_Market_Code"].isin(LEGACY_ASSETS.keys())]
    logger.info(f"Filtered to {len(df_filtered)} rows for {len(LEGACY_ASSETS)} target assets")

    if df_filtered.empty:
        logger.error("No matching rows found! Checking available codes...")
        codes = df["CFTC_Contract_Market_Code"].unique()
        logger.info(f"  Sample codes: {sorted(codes)[:50]}")
        return

    total = 0
    with SessionLocal() as session:
        for _, row in df_filtered.iterrows():
            asset_code = row["CFTC_Contract_Market_Code"]
            asset_name = LEGACY_ASSETS[asset_code]

            # Parse date
            date_raw = row.get("As_of_Date_In_Form_YYMMDD")
            if pd.isna(date_raw):
                date_raw = row.get("Report_Date_as_YYYY_MM_DD")
            if pd.isna(date_raw):
                continue
            try:
                date_parsed = pd.to_datetime(date_raw)
                date_str = date_parsed.strftime("%Y-%m-%d")
            except Exception:
                continue

            noncomm_long = safe_float(row.get("NonComm_Positions_Long_All"))
            noncomm_short = safe_float(row.get("NonComm_Positions_Short_All"))
            noncomm_spread = safe_float(row.get("NonComm_Postions_Spread_All",
                                        row.get("NonComm_Positions_Spread_All")))
            noncomm_net = (noncomm_long - noncomm_short) if noncomm_long is not None and noncomm_short is not None else None

            comm_long = safe_float(row.get("Comm_Positions_Long_All"))
            comm_short = safe_float(row.get("Comm_Positions_Short_All"))
            comm_net = (comm_long - comm_short) if comm_long is not None and comm_short is not None else None

            nonrept_long = safe_float(row.get("NonRept_Positions_Long_All"))
            nonrept_short = safe_float(row.get("NonRept_Positions_Short_All"))
            nonrept_net = (nonrept_long - nonrept_short) if nonrept_long is not None and nonrept_short is not None else None

            session.execute(UPSERT_SQL, {
                "date": date_str,
                "asset_code": asset_code,
                "asset_name": asset_name,
                "open_interest": safe_float(row.get("Open_Interest_All")),
                "noncomm_long": noncomm_long,
                "noncomm_short": noncomm_short,
                "noncomm_spread": noncomm_spread,
                "noncomm_net": noncomm_net,
                "comm_long": comm_long,
                "comm_short": comm_short,
                "comm_net": comm_net,
                "nonrept_long": nonrept_long,
                "nonrept_short": nonrept_short,
                "nonrept_net": nonrept_net,
            })
            total += 1

            if total % 1000 == 0:
                logger.info(f"  Processed {total} rows ...")

        session.commit()
        logger.info(f"Total upserted: {total} rows")

        # Verification
        result = session.execute(text("""
            SELECT asset_name, COUNT(*) as cnt, MIN(date) as first_date, MAX(date) as last_date
            FROM cftc_legacy_positions
            GROUP BY asset_name
            ORDER BY asset_name
        """))
        logger.info("=== Verification ===")
        for row in result:
            logger.info(f"  {row[0]}: {row[1]} rows, {row[2]} ~ {row[3]}")


if __name__ == "__main__":
    main()
