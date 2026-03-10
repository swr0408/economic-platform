"""
金プレミアム/ディスカウント 日次スケジューラー

GoldHub API から最新データを取得し、DB未登録分をUPSERT。

毎週火曜 JST 08:00（WGC更新: 火曜 JTC 08:00）
リトライ: 火曜 JST 12:00
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

GOLDHUB_API_URL = "https://fsapi.gold.org/api/v11/charts/local-gold-price-premiums?cache=false20250113"


def _get_latest_date_in_db() -> Optional[str]:
    """DBに格納済みの最新日付を取得"""
    try:
        try:
            from backend.core.database import SessionLocal
        except ImportError:
            from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            row = session.execute(
                text("SELECT MAX(date) FROM gold_premium")
            ).fetchone()
            if row and row[0]:
                return row[0].strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"[GoldPremiumScheduler] Could not get latest DB date: {e}")
    return None


def fetch_latest_from_api() -> list[dict]:
    """GoldHub APIから最新データを取得し、DB未登録のレコードを返す"""
    import requests

    latest_db_date = _get_latest_date_in_db()
    logger.info(f"[GoldPremiumScheduler] Latest date in DB: {latest_db_date}")

    try:
        resp = requests.get(
            GOLDHUB_API_URL,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://www.gold.org/goldhub/data/gold-premium",
            },
        )
        if resp.status_code != 200:
            logger.error(f"[GoldPremiumScheduler] API returned {resp.status_code}")
            return []

        data = resp.json()
        chart = data.get("chartData", {})

    except Exception as e:
        logger.error(f"[GoldPremiumScheduler] API fetch failed: {e}")
        return []

    # パース
    china_map: dict[str, float] = {}
    for point in chart.get("china_premdisc", []):
        if len(point) >= 2 and point[1] is not None:
            ts_ms = int(point[0])
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            china_map[dt.strftime("%Y-%m-%d")] = float(point[1])

    india_map: dict[str, float] = {}
    for point in chart.get("india_premdisc", []):
        if len(point) >= 2 and point[1] is not None:
            ts_ms = int(point[0])
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            india_map[dt.strftime("%Y-%m-%d")] = float(point[1])

    logger.info(f"[GoldPremiumScheduler] API: china={len(china_map)}, india={len(india_map)} points")

    # DB最新日付以降のみ
    all_dates = sorted(set(list(china_map.keys()) + list(india_map.keys())))
    if latest_db_date:
        all_dates = [d for d in all_dates if d >= latest_db_date]

    records = []
    for date_str in all_dates:
        records.append({
            "date": date_str,
            "china": round(china_map[date_str], 6) if date_str in china_map else None,
            "india": round(india_map[date_str], 6) if date_str in india_map else None,
        })

    logger.info(f"[GoldPremiumScheduler] {len(records)} new/updated records")
    return records


def save_to_db(records: list[dict]) -> int:
    """レコードをDBに保存 (UPSERT)"""
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
            result = session.execute(
                text("""
                    INSERT INTO gold_premium (date, china, india, source)
                    VALUES (:date, :china, :india, 'api')
                    ON CONFLICT (date) DO UPDATE SET
                        china = COALESCE(EXCLUDED.china, gold_premium.china),
                        india = COALESCE(EXCLUDED.india, gold_premium.india),
                        updated_at = NOW()
                """),
                rec,
            )
            if result.rowcount > 0:
                count += 1
        session.commit()

    return count


def clear_service_cache():
    """Redisキャッシュをクリア"""
    try:
        from backend.core.redis_client import redis_client
    except ImportError:
        from core.redis_client import redis_client

    redis_client.delete("market:gold_premium:data")
    logger.info("[GoldPremiumScheduler] Cleared Redis cache")


class GoldPremiumScheduler:
    """金プレミアム/ディスカウント 週次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    async def _run(self):
        """GoldHub APIから最新データを取得しDBに保存"""
        try:
            logger.info("[GoldPremiumScheduler] Starting update...")
            records = fetch_latest_from_api()
            if not records:
                logger.warning("[GoldPremiumScheduler] No new records")
                return

            count = save_to_db(records)
            logger.info(f"[GoldPremiumScheduler] Saved {count} records to DB")

            dates = sorted([r["date"] for r in records])
            logger.info(f"[GoldPremiumScheduler] Date range: {dates[0]} ~ {dates[-1]}")

            clear_service_cache()

        except Exception as e:
            logger.error(f"[GoldPremiumScheduler] Error: {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """スケジューラーを開始
        - 毎週火曜 08:00 JST（WGC更新後）
        - 毎週火曜 12:00 JST（リトライ）
        """
        self.scheduler.add_job(
            self._run,
            CronTrigger(day_of_week="tue", hour=8, minute=0, timezone=JST),
            id="gold_premium_weekly_08",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(day_of_week="tue", hour=12, minute=0, timezone=JST),
            id="gold_premium_weekly_12",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[GoldPremiumScheduler] Started (Tue 08:00 + 12:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


gold_premium_scheduler = GoldPremiumScheduler()
