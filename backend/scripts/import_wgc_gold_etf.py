"""
WGC (World Gold Council) 金ETF保有残高・フロー 初回インポートスクリプト

Excel (手動DL) から国別月次データを集計しDBに格納する。
金価格はJSON API (holdings-chart2) から取得。

Usage:
    cd backend
    python scripts/import_wgc_gold_etf.py
"""
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import requests

sys.path.insert(0, ".")
from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

EXCEL_PATH = Path(__file__).parent.parent / "data" / "excel" / "ETF_Flows_February_2026.xlsx"

HOLDINGS_API = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/holdings-chart2"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Excel国名 → DB国名マッピング
TARGET_COUNTRIES = {
    "US": "us",
    "UK": "uk",
    "Germany": "germany",
    "Switzerland": "switzerland",
    "Japan": "japan",
    "China P.R. Mainland": "china",
    "India": "india",
    "Australia": "australia",
    "Canada": "canada",
    "South Africa": "south_africa",
    "Hong Kong SAR": "hong_kong",
}


def parse_excel_sheet(sheet_name: str, value_field: str) -> dict:
    """
    Excelシートから国別月次データを集計。

    Returns:
        {date_str: {country_key: value, ...}, ...}
    """
    logger.info(f"Parsing sheet: {sheet_name}")
    df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name, header=None)

    # Row 4 = Country, Row 5 = Header (Date, Gold, Ounces, Tonnes, Value, Fund1, Fund2, ...)
    country_row = df.iloc[4, :]
    # Row 5, Col 1 = "Gold, US$/oz"
    # Data starts at Row 6

    # Fund columns per country (col 5 onward)
    country_cols: dict[str, list[int]] = {}
    for col_idx in range(5, df.shape[1]):
        excel_country = country_row.iloc[col_idx]
        if pd.notna(excel_country) and excel_country in TARGET_COUNTRIES:
            db_key = TARGET_COUNTRIES[excel_country]
            if db_key not in country_cols:
                country_cols[db_key] = []
            country_cols[db_key].append(col_idx)

    logger.info(f"Country fund columns: {', '.join(f'{k}={len(v)}' for k, v in country_cols.items())}")

    # Parse data rows (Row 6 onward)
    result: dict[str, dict[str, float | None]] = {}
    gold_prices: dict[str, float] = {}  # date -> gold price from Excel

    for row_idx in range(6, df.shape[0]):
        date_val = df.iloc[row_idx, 0]
        if pd.isna(date_val):
            continue

        if isinstance(date_val, datetime):
            dt = date_val
        else:
            try:
                dt = pd.to_datetime(date_val)
            except Exception:
                continue

        # 年月キーで統合（月末日付のズレを吸収）
        date_str = f"{dt.year:04d}-{dt.month:02d}"

        # Gold price (col 1)
        gold_val = df.iloc[row_idx, 1]
        if pd.notna(gold_val):
            try:
                gold_prices[date_str] = float(gold_val)
            except (ValueError, TypeError):
                pass

        country_data: dict[str, float | None] = {}
        for db_key, cols in country_cols.items():
            total = 0.0
            has_data = False
            for col_idx in cols:
                val = df.iloc[row_idx, col_idx]
                if pd.notna(val):
                    try:
                        total += float(val)
                        has_data = True
                    except (ValueError, TypeError):
                        pass
            country_data[db_key] = round(total, 4) if has_data else None

        result[date_str] = country_data

    logger.info(f"Parsed {len(result)} dates from {sheet_name}")
    return result, gold_prices


def fetch_gold_prices_from_api() -> dict[str, float]:
    """JSON APIから月次金価格を取得"""
    logger.info("Fetching gold prices from API...")
    try:
        resp = requests.get(HOLDINGS_API, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        monthly = data["chartData"]["data"]["Monthly"]["tonnes"]
        columns = monthly["columns"]

        # Find gold price column index
        gold_col_idx = None
        for i, col in enumerate(columns):
            if "Gold" in col:
                gold_col_idx = i
                break

        if gold_col_idx is None:
            logger.warning("Gold price column not found in API")
            return {}

        prices = {}
        for row in monthly["set"]:
            ts_ms = row[0]
            date_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if row[gold_col_idx] is not None:
                prices[date_str] = float(row[gold_col_idx])

        logger.info(f"Got {len(prices)} gold prices from API")
        return prices
    except Exception as e:
        logger.warning(f"Could not fetch gold prices from API: {e}")
        return {}


def _ym_to_eom(ym: str) -> str:
    """年月キー (YYYY-MM) → 月末日 (YYYY-MM-DD)"""
    import calendar
    year, month = int(ym[:4]), int(ym[5:7])
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{last_day:02d}"


def import_to_db(
    holdings: dict,
    flows: dict,
    gold_prices_excel: dict,
    gold_prices_api: dict,
) -> int:
    """国別月次データをDBにUPSERT"""
    all_dates = sorted(set(holdings.keys()) | set(flows.keys()))
    logger.info(f"Total dates to import: {len(all_dates)}")

    count = 0
    with SessionLocal() as session:
        for ym_key in all_dates:
            h = holdings.get(ym_key, {})
            f = flows.get(ym_key, {})
            date_str = _ym_to_eom(ym_key)

            # Gold price: API優先（APIキーはYYYY-MM-DD）、なければExcel
            gold_price = gold_prices_api.get(date_str)
            if gold_price is None:
                # API日付と完全一致しない場合、同年月で探す
                for api_date, price in gold_prices_api.items():
                    if api_date[:7] == ym_key:
                        gold_price = price
                        break
            if gold_price is None:
                gold_price = gold_prices_excel.get(ym_key)

            all_countries = set(list(h.keys()) + list(f.keys()))

            for country in all_countries:
                session.execute(
                    text("""
                        INSERT INTO wgc_gold_etf
                            (date, frequency, country, holdings_ton, flows_ton, flows_usd, gold_price_usd, source)
                        VALUES
                            (:date, 'monthly', :country, :holdings_ton, :flows_ton, :flows_usd, :gold_price_usd, 'WGC_EXCEL')
                        ON CONFLICT (date, frequency, country) DO UPDATE SET
                            holdings_ton = EXCLUDED.holdings_ton,
                            flows_ton = EXCLUDED.flows_ton,
                            flows_usd = EXCLUDED.flows_usd,
                            gold_price_usd = COALESCE(EXCLUDED.gold_price_usd, wgc_gold_etf.gold_price_usd),
                            updated_at = NOW()
                    """),
                    {
                        "date": date_str,
                        "country": country,
                        "holdings_ton": h.get(country),
                        "flows_ton": None,  # flows sheet is in US$mn, not tonnes
                        "flows_usd": f.get(country),
                        "gold_price_usd": gold_price,
                    },
                )
                count += 1

        session.commit()

    return count


def main():
    if not EXCEL_PATH.exists():
        logger.error(f"Excel file not found: {EXCEL_PATH}")
        sys.exit(1)

    # 1. Parse Holdings sheet (tonnes)
    holdings, gold_prices_excel = parse_excel_sheet("Holdings by month", "holdings_ton")

    # 2. Parse Flows sheet (US$mn)
    flows, _ = parse_excel_sheet("Fund flows by month", "flows_usd")

    # 3. Get gold prices from API
    gold_prices_api = fetch_gold_prices_from_api()

    # 4. Import to DB
    count = import_to_db(holdings, flows, gold_prices_excel, gold_prices_api)
    logger.info(f"Imported {count} records to wgc_gold_etf")

    # 5. Verify
    with SessionLocal() as session:
        result = session.execute(text("SELECT COUNT(*) FROM wgc_gold_etf")).fetchone()
        logger.info(f"Total records: {result[0]}")

        countries = session.execute(
            text("SELECT country, COUNT(*) FROM wgc_gold_etf GROUP BY country ORDER BY country")
        ).fetchall()
        for r in countries:
            logger.info(f"  {r[0]}: {r[1]} records")

        latest = session.execute(
            text("""
                SELECT date, country, holdings_ton, flows_usd, gold_price_usd
                FROM wgc_gold_etf
                WHERE date = (SELECT MAX(date) FROM wgc_gold_etf)
                ORDER BY holdings_ton DESC NULLS LAST
            """)
        ).fetchall()
        logger.info("Latest data:")
        for r in latest:
            logger.info(f"  {r[0]} {r[1]}: holdings={r[2]} ton, flows=${r[3]}mn, gold=${r[4]}")


if __name__ == "__main__":
    main()
