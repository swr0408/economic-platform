"""
中国金ETF残高 (518880) 日次スケジューラー

上海証券交易所のAPIから 518880 華安黄金ETF の総份額を取得し、
DB未登録の新しいデータを追加する。

毎日 JST 17:00 実行（SSE取引終了後）。リトライ: JST 19:00。

API: http://query.sse.com.cn/commonQuery.do
sqlId: COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_MOREN_L（直近）
sqlId: COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_SEARCH_L（日付指定）
"""
import json
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import requests

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")

API_URL = "http://query.sse.com.cn/commonQuery.do"
HEADERS = {
    "Host": "query.sse.com.cn",
    "Referer": "http://www.sse.com.cn/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}
FUND_CODE = "518880"
JSONP_RE = re.compile(r"cb\((.*)\)", re.DOTALL)


def _get_latest_date_in_db() -> Optional[str]:
    try:
        try:
            from backend.core.database import SessionLocal
        except ImportError:
            from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            row = session.execute(
                text("SELECT MAX(date) FROM china_gold_etf_balance")
            ).fetchone()
            if row and row[0]:
                return row[0].strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"[ChinaGoldEtfBalanceScheduler] Could not get latest DB date: {e}")
    return None


def fetch_new_data() -> list[dict]:
    """SSE APIから直近の総份額データを取得。"""
    latest_db = _get_latest_date_in_db()
    logger.info(f"[ChinaGoldEtfBalanceScheduler] Latest DB date: {latest_db}")

    # まずデフォルトAPI（直近データ）で取得
    params = {
        "jsonCallBack": "cb",
        "isPagination": "true",
        "sqlId": "COMMON_SSE_ZQPZ_ETFZL_ETFJBXX_JJGM_MOREN_L",
        "SEC_CODE": FUND_CODE,
        "pageHelp.pageSize": "50",
        "pageHelp.pageNo": "1",
    }

    try:
        r = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
        m = JSONP_RE.search(r.text)
        if not m:
            logger.error("[ChinaGoldEtfBalanceScheduler] Failed to parse JSONP")
            return []
        data = json.loads(m.group(1))
        result = data.get("result", [])
    except Exception as e:
        logger.error(f"[ChinaGoldEtfBalanceScheduler] Fetch error: {e}")
        return []

    if not result:
        logger.info("[ChinaGoldEtfBalanceScheduler] No data from SSE API")
        return []

    records = []
    for item in result:
        date_str = item.get("STAT_DATE", "")
        if not date_str:
            continue
        if latest_db and date_str <= latest_db:
            continue
        try:
            records.append({
                "date": date_str,
                "fund_code": FUND_CODE,
                "total_shares_wan": float(item["TOT_VOL"]),
            })
        except (ValueError, KeyError):
            continue

    logger.info(f"[ChinaGoldEtfBalanceScheduler] Parsed {len(records)} new records")
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
                    INSERT INTO china_gold_etf_balance
                        (date, fund_code, total_shares_wan, source)
                    VALUES
                        (:date, :fund_code, :total_shares_wan, 'SSE_API')
                    ON CONFLICT (date) DO UPDATE SET
                        total_shares_wan = EXCLUDED.total_shares_wan,
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

    redis_client.delete("market:china_gold_etf_balance:data")
    logger.info("[ChinaGoldEtfBalanceScheduler] Cleared Redis cache")


class ChinaGoldEtfBalanceScheduler:
    """中国金ETF残高 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    async def _run(self):
        # ブロッキング I/O (requests/sync DB) をワーカースレッドへ退避。
        # 直接実行するとイベントループを占有し login 等が応答不能になる。
        await asyncio.to_thread(self._run_sync)

    def _run_sync(self):
        try:
            logger.info("[ChinaGoldEtfBalanceScheduler] Starting daily update...")
            records = fetch_new_data()
            if not records:
                logger.info("[ChinaGoldEtfBalanceScheduler] No new records")
                return

            count = save_to_db(records)
            logger.info(f"[ChinaGoldEtfBalanceScheduler] Saved {count} records")

            clear_service_cache()

        except Exception as e:
            logger.error(f"[ChinaGoldEtfBalanceScheduler] Error: {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """毎日 17:05 JST + リトライ 19:05 JST + 起動時キャッチアップ (DBが2日以上古ければ)"""
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=17, minute=5, timezone=JST),
            id="china_gold_etf_balance_daily_17",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=19, minute=5, timezone=JST),
            id="china_gold_etf_balance_daily_19",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # 起動時キャッチアップ
        latest_db_str = _get_latest_date_in_db()
        should_catchup = True
        if latest_db_str:
            try:
                latest_dt = datetime.strptime(latest_db_str, "%Y-%m-%d").date()
                age_days = (date.today() - latest_dt).days
                should_catchup = age_days >= 2
                logger.info(f"[ChinaGoldEtfBalanceScheduler] DB latest: {latest_db_str} ({age_days}d old)")
            except ValueError:
                pass
        if should_catchup:
            self.scheduler.add_job(
                self._run,
                "date",
                run_date=datetime.now(JST) + timedelta(seconds=30),
                id="china_gold_etf_balance_startup_catchup",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info("[ChinaGoldEtfBalanceScheduler] Startup catch-up scheduled (in 30s)")

        self.scheduler.start()
        logger.info("[ChinaGoldEtfBalanceScheduler] Started (Daily 17:05 + 19:05 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


china_gold_etf_balance_scheduler = ChinaGoldEtfBalanceScheduler()
