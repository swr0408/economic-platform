"""
WGC 金ETFフロー/保有残高 週次スケジューラー

fsapi.gold.org の archive-tablegroup API から国別スナップショットを取得し、
DB未登録の新しいデータを追加する。

- Monthly: DB最新月より新しければUPSERT
- Weekly: 毎週の国別スナップショットをDB積み上げ

毎週火曜 JST 08:00 実行。リトライ: JST 12:00。
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

ARCHIVE_URL = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/archive-tablegroup/all"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# archive API国名 → DB国名マッピング
COUNTRY_MAP = {
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


def _get_latest_date_in_db(frequency: str) -> Optional[str]:
    """DBに格納済みの最新日付を取得"""
    try:
        try:
            from backend.core.database import SessionLocal
        except ImportError:
            from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            row = session.execute(
                text("SELECT MAX(date) FROM wgc_gold_etf WHERE frequency = :freq"),
                {"freq": frequency},
            ).fetchone()
            if row and row[0]:
                return row[0].strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"[WgcGoldEtfScheduler] Could not get latest DB date ({frequency}): {e}")
    return None


def _parse_table(table_data: dict) -> list[dict]:
    """archive-tablegroup の countries テーブル1件をパースしてレコードリストを返す。

    API構造:
        table_data = {
            "data": {
                "columns": ["Country", "AUM <br/>(bn)", "Fund Flows <br/>(US$mn)",
                            "Holdings <br/>(tonnes)", "Demand <br/>(tonnes)",
                            "Demand <br/>(% of holdings)"],
                "0": ["US", "350.52", "4595.81", "2087.49", "27.15", "1.32"],
                "1": ["UK", "102.92", "..."],
                ...
            },
            "asOfDate": "2026-02-28",
            "periodTitle": "Feb 26"
        }
    """
    as_of_date = table_data.get("asOfDate")
    if not as_of_date:
        return []

    data_obj = table_data.get("data", {})
    columns = data_obj.get("columns", [])
    if not columns:
        return []

    # カラムインデックス特定（HTML <br/> を含む場合がある）
    holdings_idx = None
    flows_idx = None
    for i, col in enumerate(columns):
        col_clean = col.replace("<br/>", " ").replace("<br>", " ")
        if "Holdings" in col_clean and "tonnes" in col_clean:
            holdings_idx = i
        elif "Fund Flows" in col_clean and "US$mn" in col_clean:
            flows_idx = i

    if holdings_idx is None and flows_idx is None:
        logger.warning(f"[WgcGoldEtfScheduler] Could not find Holdings/Flows columns in {columns}")
        return []

    records = []

    # 行は文字列数値キー "0", "1", "2", ...
    row_idx = 0
    while True:
        row = data_obj.get(str(row_idx))
        if row is None:
            break
        row_idx += 1

        if not row or len(row) < 1:
            continue

        country_name = str(row[0]).strip()
        if country_name not in COUNTRY_MAP:
            continue

        db_country = COUNTRY_MAP[country_name]
        holdings_ton = None
        flows_usd = None

        if holdings_idx is not None and holdings_idx < len(row):
            val = row[holdings_idx]
            if val is not None and str(val).strip() != "":
                try:
                    holdings_ton = float(val)
                except (ValueError, TypeError):
                    pass

        if flows_idx is not None and flows_idx < len(row):
            val = row[flows_idx]
            if val is not None and str(val).strip() != "":
                try:
                    flows_usd = float(val)
                except (ValueError, TypeError):
                    pass

        if holdings_ton is not None or flows_usd is not None:
            records.append({
                "date": as_of_date,
                "country": db_country,
                "holdings_ton": holdings_ton,
                "flows_usd": flows_usd,
            })

    return records


def fetch_new_data() -> tuple[list[dict], list[dict]]:
    """archive-tablegroup APIから国別スナップショットを取得。

    Returns:
        (monthly_records, weekly_records)
    """
    logger.info("[WgcGoldEtfScheduler] Fetching archive-tablegroup/all...")
    try:
        resp = requests.get(ARCHIVE_URL, headers=HEADERS, timeout=60)
        if resp.status_code != 200:
            logger.error(f"[WgcGoldEtfScheduler] HTTP {resp.status_code}")
            return [], []
        api_data = resp.json()
    except Exception as e:
        logger.error(f"[WgcGoldEtfScheduler] Fetch error: {e}")
        return [], []

    try:
        countries_data = api_data["chartData"]["data"]["countries"]
    except (KeyError, TypeError) as e:
        logger.error(f"[WgcGoldEtfScheduler] Unexpected JSON structure: {e}")
        return [], []

    # Monthly
    monthly_records = []
    monthly_table = countries_data.get("Monthly")
    if monthly_table:
        latest_monthly_db = _get_latest_date_in_db("monthly")
        records = _parse_table(monthly_table)
        as_of = monthly_table.get("asOfDate", "")
        if records:
            if latest_monthly_db and as_of <= latest_monthly_db:
                logger.info(f"[WgcGoldEtfScheduler] Monthly {as_of} already in DB (latest={latest_monthly_db}), skipping")
            else:
                monthly_records = records
                logger.info(f"[WgcGoldEtfScheduler] Monthly {as_of}: {len(records)} country records")

    # Weekly
    weekly_records = []
    weekly_table = countries_data.get("Weekly")
    if weekly_table:
        latest_weekly_db = _get_latest_date_in_db("weekly")
        records = _parse_table(weekly_table)
        as_of = weekly_table.get("asOfDate", "")
        if records:
            if latest_weekly_db and as_of <= latest_weekly_db:
                logger.info(f"[WgcGoldEtfScheduler] Weekly {as_of} already in DB (latest={latest_weekly_db}), skipping")
            else:
                weekly_records = records
                logger.info(f"[WgcGoldEtfScheduler] Weekly {as_of}: {len(records)} country records")

    return monthly_records, weekly_records


def _get_gold_price_from_holdings_api() -> Optional[float]:
    """holdings-chart2 APIから最新の金価格を取得"""
    try:
        url = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/holdings-chart2"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return None
        data = resp.json()
        monthly = data["chartData"]["data"]["Monthly"]["tonnes"]
        columns = monthly["columns"]
        gold_col_idx = None
        for i, col in enumerate(columns):
            if "Gold" in col:
                gold_col_idx = i
                break
        if gold_col_idx is None:
            return None
        last_row = monthly["set"][-1]
        if last_row[gold_col_idx] is not None:
            return float(last_row[gold_col_idx])
    except Exception:
        pass
    return None


def save_to_db(monthly_records: list[dict], weekly_records: list[dict]) -> int:
    if not monthly_records and not weekly_records:
        return 0

    try:
        from backend.core.database import SessionLocal
    except ImportError:
        from core.database import SessionLocal
    from sqlalchemy import text

    gold_price = _get_gold_price_from_holdings_api()

    count = 0
    with SessionLocal() as session:
        for rec in monthly_records:
            session.execute(
                text("""
                    INSERT INTO wgc_gold_etf
                        (date, frequency, country, holdings_ton, flows_ton,
                         flows_usd, gold_price_usd, source)
                    VALUES
                        (:date, 'monthly', :country, :holdings_ton, NULL,
                         :flows_usd, :gold_price_usd, 'WGC_API')
                    ON CONFLICT (date, frequency, country) DO UPDATE SET
                        holdings_ton = COALESCE(EXCLUDED.holdings_ton, wgc_gold_etf.holdings_ton),
                        flows_usd = COALESCE(EXCLUDED.flows_usd, wgc_gold_etf.flows_usd),
                        gold_price_usd = COALESCE(EXCLUDED.gold_price_usd, wgc_gold_etf.gold_price_usd),
                        updated_at = NOW()
                """),
                {**rec, "gold_price_usd": gold_price},
            )
            count += 1

        for rec in weekly_records:
            session.execute(
                text("""
                    INSERT INTO wgc_gold_etf
                        (date, frequency, country, holdings_ton, flows_ton,
                         flows_usd, gold_price_usd, source)
                    VALUES
                        (:date, 'weekly', :country, :holdings_ton, NULL,
                         :flows_usd, :gold_price_usd, 'WGC_API')
                    ON CONFLICT (date, frequency, country) DO UPDATE SET
                        holdings_ton = COALESCE(EXCLUDED.holdings_ton, wgc_gold_etf.holdings_ton),
                        flows_usd = COALESCE(EXCLUDED.flows_usd, wgc_gold_etf.flows_usd),
                        gold_price_usd = COALESCE(EXCLUDED.gold_price_usd, wgc_gold_etf.gold_price_usd),
                        updated_at = NOW()
                """),
                {**rec, "gold_price_usd": gold_price},
            )
            count += 1

        session.commit()

    return count


def clear_service_cache():
    try:
        from backend.core.redis_client import redis_client
    except ImportError:
        from core.redis_client import redis_client

    for dt in ["holdings_ton", "flows_usd"]:
        redis_client.delete(f"market:wgc_gold_etf:{dt}")
    logger.info("[WgcGoldEtfScheduler] Cleared Redis cache")


class WgcGoldEtfScheduler:
    """WGC 金ETFフロー/保有残高 週次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    async def _run(self):
        try:
            logger.info("[WgcGoldEtfScheduler] Starting weekly update...")
            monthly_records, weekly_records = fetch_new_data()
            if not monthly_records and not weekly_records:
                logger.warning("[WgcGoldEtfScheduler] No new records")
                return

            count = save_to_db(monthly_records, weekly_records)
            logger.info(
                f"[WgcGoldEtfScheduler] Saved {count} records "
                f"(monthly={len(monthly_records)}, weekly={len(weekly_records)})"
            )

            clear_service_cache()

        except Exception as e:
            logger.error(f"[WgcGoldEtfScheduler] Error: {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """毎週火曜 08:00 JST + リトライ 12:00 JST + 起動時キャッチアップ (週次データ8日以上古ければ)"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(day_of_week="tue", hour=8, minute=0, timezone=JST),
            id="wgc_gold_etf_weekly_08",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(day_of_week="tue", hour=12, minute=0, timezone=JST),
            id="wgc_gold_etf_weekly_12",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # 起動時キャッチアップ (週次データなので8日以上古ければ即時実行)
        latest_db_str = _get_latest_date_in_db("weekly")
        should_catchup = True
        if latest_db_str:
            try:
                latest_dt = datetime.strptime(latest_db_str, "%Y-%m-%d").date()
                age_days = (date.today() - latest_dt).days
                should_catchup = age_days >= 8
                logger.info(f"[WgcGoldEtfScheduler] DB weekly latest: {latest_db_str} ({age_days}d old)")
            except ValueError:
                pass
        if should_catchup:
            self.scheduler.add_job(
                self._run,
                "date",
                run_date=datetime.now(JST) + timedelta(seconds=30),
                id="wgc_gold_etf_startup_catchup",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info("[WgcGoldEtfScheduler] Startup catch-up scheduled (in 30s)")

        self.scheduler.start()
        logger.info("[WgcGoldEtfScheduler] Started (Tue 08:00 + 12:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


wgc_gold_etf_scheduler = WgcGoldEtfScheduler()
