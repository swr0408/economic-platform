"""
SGE Au(T+D) 日次スケジューラー

上海黄金取引所のダウンロードAPIから Au(T+D) の日次行情データを取得し、
DB未登録の新しいデータを追加する。

毎日 JST 17:00 実行（SGE取引終了後）。リトライ: JST 19:00。
"""
import io
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")

DOWNLOAD_URL = (
    "https://www.sge.com.cn/portal/marketAutomation/"
    "downloadExcelForQuoteDailyNew"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.sge.com.cn/sjzx/quotation_daily_new",
}


def _get_latest_date_in_db() -> Optional[str]:
    try:
        try:
            from backend.core.database import SessionLocal
        except ImportError:
            from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            row = session.execute(
                text("SELECT MAX(date) FROM sge_au_td")
            ).fetchone()
            if row and row[0]:
                return row[0].strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"[SgeGoldScheduler] Could not get latest DB date: {e}")
    return None


def fetch_new_data() -> list[dict]:
    """SGEダウンロードAPIから最新Au(T+D)日次データを取得。"""
    latest_db = _get_latest_date_in_db()

    if latest_db:
        start_date = latest_db
    else:
        start_date = "2024-01-01"

    end_date = datetime.now(CST).strftime("%Y-%m-%d")

    logger.info(
        f"[SgeGoldScheduler] Fetching Au(T+D) data: {start_date} ~ {end_date}"
    )

    try:
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "inst_ids": "Au(T+D)",
        }
        resp = requests.get(
            DOWNLOAD_URL, params=params, headers=HEADERS, timeout=60
        )
        if resp.status_code != 200:
            logger.error(f"[SgeGoldScheduler] HTTP {resp.status_code}")
            return []

        content_type = resp.headers.get("Content-Type", "")
        if "application" not in content_type and "octet" not in content_type:
            logger.error(
                f"[SgeGoldScheduler] Unexpected content type: {content_type}"
            )
            return []

    except Exception as e:
        logger.error(f"[SgeGoldScheduler] Fetch error: {e}")
        return []

    try:
        df = pd.read_excel(io.BytesIO(resp.content), header=0)
    except Exception as e:
        logger.error(f"[SgeGoldScheduler] Excel parse error: {e}")
        return []

    if df.empty:
        logger.info("[SgeGoldScheduler] No data in response")
        return []

    records = []
    for _, row in df.iterrows():
        try:
            date_val = row.iloc[1]
            if pd.isna(date_val):
                continue

            if isinstance(date_val, str):
                date_str = date_val.strip()
            else:
                date_str = pd.Timestamp(date_val).strftime("%Y-%m-%d")

            # Skip dates already in DB
            if latest_db and date_str <= latest_db:
                continue

            def safe_float(val):
                if pd.isna(val):
                    return None
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

            def safe_int(val):
                if pd.isna(val):
                    return None
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    return None

            record = {
                "date": date_str,
                "open_price": safe_float(row.iloc[3]),
                "high_price": safe_float(row.iloc[4]),
                "low_price": safe_float(row.iloc[5]),
                "close_price": safe_float(row.iloc[6]),
                "settlement_price": safe_float(row.iloc[9]),
                "volume_kg": safe_float(row.iloc[10]),
                "amount_cny": safe_float(row.iloc[11]),
                "open_interest": safe_int(row.iloc[12]),
            }
            records.append(record)
        except Exception:
            continue

    logger.info(f"[SgeGoldScheduler] Parsed {len(records)} new records")
    return records


def save_to_db(records: list[dict]) -> int:
    if not records:
        return 0

    try:
        from backend.core.database import SessionLocal
    except ImportError:
        from core.database import SessionLocal
    from sqlalchemy import text

    count = 0
    with SessionLocal() as session:
        for rec in records:
            session.execute(
                text("""
                    INSERT INTO sge_au_td
                        (date, open_price, high_price, low_price, close_price,
                         settlement_price, volume_kg, amount_cny, open_interest, source)
                    VALUES
                        (:date, :open_price, :high_price, :low_price, :close_price,
                         :settlement_price, :volume_kg, :amount_cny, :open_interest, 'SGE_API')
                    ON CONFLICT (date) DO UPDATE SET
                        open_price = COALESCE(EXCLUDED.open_price, sge_au_td.open_price),
                        high_price = COALESCE(EXCLUDED.high_price, sge_au_td.high_price),
                        low_price = COALESCE(EXCLUDED.low_price, sge_au_td.low_price),
                        close_price = COALESCE(EXCLUDED.close_price, sge_au_td.close_price),
                        settlement_price = COALESCE(EXCLUDED.settlement_price, sge_au_td.settlement_price),
                        volume_kg = COALESCE(EXCLUDED.volume_kg, sge_au_td.volume_kg),
                        amount_cny = COALESCE(EXCLUDED.amount_cny, sge_au_td.amount_cny),
                        open_interest = COALESCE(EXCLUDED.open_interest, sge_au_td.open_interest),
                        updated_at = NOW()
                """),
                rec,
            )
            count += 1
        session.commit()

    return count


def clear_service_cache():
    try:
        from backend.core.redis_client import redis_client
    except ImportError:
        from core.redis_client import redis_client

    redis_client.delete("market:sge_gold:data")
    logger.info("[SgeGoldScheduler] Cleared Redis cache")


class SgeGoldScheduler:
    """SGE Au(T+D) 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    async def _run(self):
        try:
            logger.info("[SgeGoldScheduler] Starting daily update...")
            records = fetch_new_data()
            if not records:
                logger.info("[SgeGoldScheduler] No new records")
                return

            count = save_to_db(records)
            logger.info(f"[SgeGoldScheduler] Saved {count} records")

            clear_service_cache()

        except Exception as e:
            logger.error(f"[SgeGoldScheduler] Error: {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """毎日 17:00 JST + リトライ 19:00 JST"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=17, minute=0, timezone=JST),
            id="sge_gold_daily_17",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=19, minute=0, timezone=JST),
            id="sge_gold_daily_19",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[SgeGoldScheduler] Started (Daily 17:00 + 19:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


sge_gold_scheduler = SgeGoldScheduler()
