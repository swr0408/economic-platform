"""
CFTC TFF (Traders in Financial Futures) データインポート
CFTC PRE APIから全期間のTFFデータをダウンロードし、対象19銘柄をDBへ格納
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

TFF_API_URL = "https://publicreporting.cftc.gov/api/views/gpe5-46if/rows.csv?accessType=DOWNLOAD"

# CFTC Contract Market Code → asset_name
TFF_ASSETS = {
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
    INSERT INTO cftc_tff_positions (
        date, asset_code, asset_name, open_interest,
        dealer_long, dealer_short, dealer_spread, dealer_net,
        asset_mgr_long, asset_mgr_short, asset_mgr_spread, asset_mgr_net,
        lev_money_long, lev_money_short, lev_money_spread, lev_money_net,
        other_long, other_short, other_spread, other_net,
        nonrept_long, nonrept_short, nonrept_net,
        source
    ) VALUES (
        :date, :asset_code, :asset_name, :open_interest,
        :dealer_long, :dealer_short, :dealer_spread, :dealer_net,
        :asset_mgr_long, :asset_mgr_short, :asset_mgr_spread, :asset_mgr_net,
        :lev_money_long, :lev_money_short, :lev_money_spread, :lev_money_net,
        :other_long, :other_short, :other_spread, :other_net,
        :nonrept_long, :nonrept_short, :nonrept_net,
        'CFTC'
    )
    ON CONFLICT (date, asset_code) DO UPDATE SET
        asset_name = EXCLUDED.asset_name,
        open_interest = COALESCE(EXCLUDED.open_interest, cftc_tff_positions.open_interest),
        dealer_long = COALESCE(EXCLUDED.dealer_long, cftc_tff_positions.dealer_long),
        dealer_short = COALESCE(EXCLUDED.dealer_short, cftc_tff_positions.dealer_short),
        dealer_spread = COALESCE(EXCLUDED.dealer_spread, cftc_tff_positions.dealer_spread),
        dealer_net = COALESCE(EXCLUDED.dealer_net, cftc_tff_positions.dealer_net),
        asset_mgr_long = COALESCE(EXCLUDED.asset_mgr_long, cftc_tff_positions.asset_mgr_long),
        asset_mgr_short = COALESCE(EXCLUDED.asset_mgr_short, cftc_tff_positions.asset_mgr_short),
        asset_mgr_spread = COALESCE(EXCLUDED.asset_mgr_spread, cftc_tff_positions.asset_mgr_spread),
        asset_mgr_net = COALESCE(EXCLUDED.asset_mgr_net, cftc_tff_positions.asset_mgr_net),
        lev_money_long = COALESCE(EXCLUDED.lev_money_long, cftc_tff_positions.lev_money_long),
        lev_money_short = COALESCE(EXCLUDED.lev_money_short, cftc_tff_positions.lev_money_short),
        lev_money_spread = COALESCE(EXCLUDED.lev_money_spread, cftc_tff_positions.lev_money_spread),
        lev_money_net = COALESCE(EXCLUDED.lev_money_net, cftc_tff_positions.lev_money_net),
        other_long = COALESCE(EXCLUDED.other_long, cftc_tff_positions.other_long),
        other_short = COALESCE(EXCLUDED.other_short, cftc_tff_positions.other_short),
        other_spread = COALESCE(EXCLUDED.other_spread, cftc_tff_positions.other_spread),
        other_net = COALESCE(EXCLUDED.other_net, cftc_tff_positions.other_net),
        nonrept_long = COALESCE(EXCLUDED.nonrept_long, cftc_tff_positions.nonrept_long),
        nonrept_short = COALESCE(EXCLUDED.nonrept_short, cftc_tff_positions.nonrept_short),
        nonrept_net = COALESCE(EXCLUDED.nonrept_net, cftc_tff_positions.nonrept_net),
        updated_at = NOW()
""")


def safe_float(val):
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def download_tff_data() -> pd.DataFrame:
    """Download full TFF dataset from CFTC PRE API."""
    logger.info(f"Downloading TFF data from {TFF_API_URL} ...")
    resp = requests.get(TFF_API_URL, timeout=300)
    resp.raise_for_status()
    logger.info(f"  Downloaded {len(resp.content) / 1024 / 1024:.1f} MB")

    df = pd.read_csv(io.StringIO(resp.text))
    logger.info(f"  Total rows: {len(df)}, Columns: {len(df.columns)}")
    return df


def main():
    df = download_tff_data()

    # Normalize code column
    df["CFTC_Contract_Market_Code"] = df["CFTC_Contract_Market_Code"].astype(str).str.strip()

    # Filter target assets
    df_filtered = df[df["CFTC_Contract_Market_Code"].isin(TFF_ASSETS.keys())]
    logger.info(f"Filtered to {len(df_filtered)} rows for {len(TFF_ASSETS)} target assets")

    total = 0
    with SessionLocal() as session:
        for _, row in df_filtered.iterrows():
            asset_code = row["CFTC_Contract_Market_Code"]
            asset_name = TFF_ASSETS[asset_code]

            # Parse date - TFF format: "MM/DD/YYYY HH:MM:SS AM"
            date_raw = row.get("Report_Date_as_YYYY_MM_DD")
            if pd.isna(date_raw):
                continue
            try:
                date_parsed = pd.to_datetime(date_raw)
                date_str = date_parsed.strftime("%Y-%m-%d")
            except Exception:
                continue

            dealer_long = safe_float(row.get("Dealer_Positions_Long_All"))
            dealer_short = safe_float(row.get("Dealer_Positions_Short_All"))
            dealer_spread = safe_float(row.get("Dealer_Positions_Spread_All"))
            dealer_net = (dealer_long - dealer_short) if dealer_long is not None and dealer_short is not None else None

            asset_mgr_long = safe_float(row.get("Asset_Mgr_Positions_Long_All"))
            asset_mgr_short = safe_float(row.get("Asset_Mgr_Positions_Short_All"))
            asset_mgr_spread = safe_float(row.get("Asset_Mgr_Positions_Spread_All"))
            asset_mgr_net = (asset_mgr_long - asset_mgr_short) if asset_mgr_long is not None and asset_mgr_short is not None else None

            lev_money_long = safe_float(row.get("Lev_Money_Positions_Long_All"))
            lev_money_short = safe_float(row.get("Lev_Money_Positions_Short_All"))
            lev_money_spread = safe_float(row.get("Lev_Money_Positions_Spread_All"))
            lev_money_net = (lev_money_long - lev_money_short) if lev_money_long is not None and lev_money_short is not None else None

            other_long = safe_float(row.get("Other_Rept_Positions_Long_All"))
            other_short = safe_float(row.get("Other_Rept_Positions_Short_All"))
            other_spread = safe_float(row.get("Other_Rept_Positions_Spread_All"))
            other_net = (other_long - other_short) if other_long is not None and other_short is not None else None

            nonrept_long = safe_float(row.get("NonRept_Positions_Long_All"))
            nonrept_short = safe_float(row.get("NonRept_Positions_Short_All"))
            nonrept_net = (nonrept_long - nonrept_short) if nonrept_long is not None and nonrept_short is not None else None

            session.execute(UPSERT_SQL, {
                "date": date_str,
                "asset_code": asset_code,
                "asset_name": asset_name,
                "open_interest": safe_float(row.get("Open_Interest_All")),
                "dealer_long": dealer_long,
                "dealer_short": dealer_short,
                "dealer_spread": dealer_spread,
                "dealer_net": dealer_net,
                "asset_mgr_long": asset_mgr_long,
                "asset_mgr_short": asset_mgr_short,
                "asset_mgr_spread": asset_mgr_spread,
                "asset_mgr_net": asset_mgr_net,
                "lev_money_long": lev_money_long,
                "lev_money_short": lev_money_short,
                "lev_money_spread": lev_money_spread,
                "lev_money_net": lev_money_net,
                "other_long": other_long,
                "other_short": other_short,
                "other_spread": other_spread,
                "other_net": other_net,
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
            FROM cftc_tff_positions
            GROUP BY asset_name
            ORDER BY asset_name
        """))
        logger.info("=== Verification ===")
        for row in result:
            logger.info(f"  {row[0]}: {row[1]} rows, {row[2]} ~ {row[3]}")


if __name__ == "__main__":
    main()
