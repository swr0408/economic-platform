"""
CFTC Disaggregated Futures データインポート
Excel 12ファイル (F_DisAgg06_15 ~ F_DisAgg26) からコモディティ6銘柄を抽出しDBへ格納
"""

import sys
import os
import logging
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EXCEL_DIR = Path(__file__).parent.parent / "data" / "excel"

EXCEL_FILES = [
    "F_DisAgg06_15.xls",
    "F_DisAgg16_16.xls",
    "F_DisAgg17.xls",
    "F_DisAgg18.xls",
    "F_DisAgg19.xls",
    "F_DisAgg20.xls",
    "F_DisAgg21.xls",
    "F_DisAgg22.xls",
    "F_DisAgg23.xls",
    "F_DisAgg24.xls",
    "F_DisAgg25.xls",
    "F_DisAgg26.xls",
]

# CFTC Contract Market Code → asset_name
DISAGG_ASSETS = {
    "088691": "gold",
    "084691": "silver",
    "085692": "copper",
    "067651": "crude_oil",
    "06765T": "brent",
    "023651": "natural_gas",
}

UPSERT_SQL = text("""
    INSERT INTO cftc_disagg_positions (
        date, asset_code, asset_name, open_interest,
        mm_long, mm_short, mm_spread, mm_net,
        pm_long, pm_short, pm_net,
        swap_long, swap_short, swap_spread, swap_net,
        other_long, other_short, other_spread, other_net,
        nonrept_long, nonrept_short, nonrept_net,
        source
    ) VALUES (
        :date, :asset_code, :asset_name, :open_interest,
        :mm_long, :mm_short, :mm_spread, :mm_net,
        :pm_long, :pm_short, :pm_net,
        :swap_long, :swap_short, :swap_spread, :swap_net,
        :other_long, :other_short, :other_spread, :other_net,
        :nonrept_long, :nonrept_short, :nonrept_net,
        'CFTC'
    )
    ON CONFLICT (date, asset_code) DO UPDATE SET
        asset_name = EXCLUDED.asset_name,
        open_interest = COALESCE(EXCLUDED.open_interest, cftc_disagg_positions.open_interest),
        mm_long = COALESCE(EXCLUDED.mm_long, cftc_disagg_positions.mm_long),
        mm_short = COALESCE(EXCLUDED.mm_short, cftc_disagg_positions.mm_short),
        mm_spread = COALESCE(EXCLUDED.mm_spread, cftc_disagg_positions.mm_spread),
        mm_net = COALESCE(EXCLUDED.mm_net, cftc_disagg_positions.mm_net),
        pm_long = COALESCE(EXCLUDED.pm_long, cftc_disagg_positions.pm_long),
        pm_short = COALESCE(EXCLUDED.pm_short, cftc_disagg_positions.pm_short),
        pm_net = COALESCE(EXCLUDED.pm_net, cftc_disagg_positions.pm_net),
        swap_long = COALESCE(EXCLUDED.swap_long, cftc_disagg_positions.swap_long),
        swap_short = COALESCE(EXCLUDED.swap_short, cftc_disagg_positions.swap_short),
        swap_spread = COALESCE(EXCLUDED.swap_spread, cftc_disagg_positions.swap_spread),
        swap_net = COALESCE(EXCLUDED.swap_net, cftc_disagg_positions.swap_net),
        other_long = COALESCE(EXCLUDED.other_long, cftc_disagg_positions.other_long),
        other_short = COALESCE(EXCLUDED.other_short, cftc_disagg_positions.other_short),
        other_spread = COALESCE(EXCLUDED.other_spread, cftc_disagg_positions.other_spread),
        other_net = COALESCE(EXCLUDED.other_net, cftc_disagg_positions.other_net),
        nonrept_long = COALESCE(EXCLUDED.nonrept_long, cftc_disagg_positions.nonrept_long),
        nonrept_short = COALESCE(EXCLUDED.nonrept_short, cftc_disagg_positions.nonrept_short),
        nonrept_net = COALESCE(EXCLUDED.nonrept_net, cftc_disagg_positions.nonrept_net),
        updated_at = NOW()
""")


def safe_float(val):
    """Convert to float, return None if not numeric."""
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def process_excel(filepath: Path, session) -> int:
    """Process one Excel file and upsert rows."""
    logger.info(f"Reading {filepath.name} ...")
    df = pd.read_excel(filepath)

    # Normalize CFTC_Contract_Market_Code to string, strip whitespace
    df["CFTC_Contract_Market_Code"] = df["CFTC_Contract_Market_Code"].astype(str).str.strip()

    # Filter only target assets
    df_filtered = df[df["CFTC_Contract_Market_Code"].isin(DISAGG_ASSETS.keys())]
    logger.info(f"  Found {len(df_filtered)} rows for target assets in {filepath.name}")

    count = 0
    for _, row in df_filtered.iterrows():
        asset_code = row["CFTC_Contract_Market_Code"]
        asset_name = DISAGG_ASSETS[asset_code]

        # Parse date
        date_val = row.get("Report_Date_as_MM_DD_YYYY")
        if pd.isna(date_val):
            continue
        if isinstance(date_val, pd.Timestamp):
            date_str = date_val.strftime("%Y-%m-%d")
        else:
            date_str = str(date_val)

        mm_long = safe_float(row.get("M_Money_Positions_Long_ALL"))
        mm_short = safe_float(row.get("M_Money_Positions_Short_ALL"))
        mm_spread = safe_float(row.get("M_Money_Positions_Spread_ALL"))
        mm_net = (mm_long - mm_short) if mm_long is not None and mm_short is not None else None

        pm_long = safe_float(row.get("Prod_Merc_Positions_Long_ALL"))
        pm_short = safe_float(row.get("Prod_Merc_Positions_Short_ALL"))
        pm_net = (pm_long - pm_short) if pm_long is not None and pm_short is not None else None

        swap_long = safe_float(row.get("Swap_Positions_Long_All"))
        # Note: CFTC data has double underscore typo
        swap_short = safe_float(row.get("Swap__Positions_Short_All", row.get("Swap_Positions_Short_All")))
        swap_spread = safe_float(row.get("Swap__Positions_Spread_All", row.get("Swap_Positions_Spread_All")))
        swap_net = (swap_long - swap_short) if swap_long is not None and swap_short is not None else None

        other_long = safe_float(row.get("Other_Rept_Positions_Long_ALL"))
        other_short = safe_float(row.get("Other_Rept_Positions_Short_ALL"))
        other_spread = safe_float(row.get("Other_Rept_Positions_Spread_ALL"))
        other_net = (other_long - other_short) if other_long is not None and other_short is not None else None

        nonrept_long = safe_float(row.get("NonRept_Positions_Long_All"))
        nonrept_short = safe_float(row.get("NonRept_Positions_Short_All"))
        nonrept_net = (nonrept_long - nonrept_short) if nonrept_long is not None and nonrept_short is not None else None

        session.execute(UPSERT_SQL, {
            "date": date_str,
            "asset_code": asset_code,
            "asset_name": asset_name,
            "open_interest": safe_float(row.get("Open_Interest_All")),
            "mm_long": mm_long,
            "mm_short": mm_short,
            "mm_spread": mm_spread,
            "mm_net": mm_net,
            "pm_long": pm_long,
            "pm_short": pm_short,
            "pm_net": pm_net,
            "swap_long": swap_long,
            "swap_short": swap_short,
            "swap_spread": swap_spread,
            "swap_net": swap_net,
            "other_long": other_long,
            "other_short": other_short,
            "other_spread": other_spread,
            "other_net": other_net,
            "nonrept_long": nonrept_long,
            "nonrept_short": nonrept_short,
            "nonrept_net": nonrept_net,
        })
        count += 1

    return count


def main():
    total = 0
    with SessionLocal() as session:
        for filename in EXCEL_FILES:
            filepath = EXCEL_DIR / filename
            if not filepath.exists():
                logger.warning(f"  File not found: {filepath}")
                continue
            count = process_excel(filepath, session)
            total += count
            logger.info(f"  Upserted {count} rows from {filename}")

        session.commit()
        logger.info(f"Total upserted: {total} rows")

        # Verification
        result = session.execute(text("""
            SELECT asset_name, COUNT(*) as cnt, MIN(date) as first_date, MAX(date) as last_date
            FROM cftc_disagg_positions
            GROUP BY asset_name
            ORDER BY asset_name
        """))
        logger.info("=== Verification ===")
        for row in result:
            logger.info(f"  {row[0]}: {row[1]} rows, {row[2]} ~ {row[3]}")


if __name__ == "__main__":
    main()
