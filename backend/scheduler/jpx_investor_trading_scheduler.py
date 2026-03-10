"""
投資部門別売買状況 週次スケジューラー

JPXは毎週第4営業日（通常は木曜日）15:30 に資料を掲載。
祝日等で非営業日がある場合はその分後ろ倒し。

毎週木曜 16:00 JST に JPX index page から最新XLSをスクレイピングし
DBに UPSERT する。念のため金曜 10:00 にもリトライ実行。

https://www.jpx.co.jp/markets/statistics-equities/investor-type/index.html
"""
import io
import re
import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

JPX_BASE = "https://www.jpx.co.jp"
JPX_INDEX_URL = f"{JPX_BASE}/markets/statistics-equities/investor-type/index.html"

# XLS行位置マッピング (0-based pandas index) - 年によって変動あり
ROW_POSITIONS = {
    "proprietary": [12, 13],
    "individuals": [26, 27],
    "foreigners": [29, 30, 31],
    "investment_trusts": [37, 38],
    "business_corps": [41, 42],
    "trust_banks": [57, 58],
}
NET_COL = 10


def _parse_value(val) -> Optional[int]:
    """カンマ付き・全角マイナス対応の値パース"""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s == "-" or s == "−":
        return None
    s = s.replace("−", "-").replace("–", "-")
    s = s.replace(",", "")
    s = s.strip('"').strip("'")
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return None


def _parse_date_from_xls(df: pd.DataFrame) -> Optional[str]:
    """XLSのRow 3, Col 0から日付を抽出"""
    raw = df.iloc[3, 0]
    if pd.isna(raw):
        return None
    raw = str(raw)
    match_paren = re.search(r"\(\s*(\d+)/(\d+)\s*-\s*(\d+)/(\d+)\s*\)", raw)
    year_match = re.search(r"(\d{4})", raw)
    if match_paren and year_match:
        year = int(year_match.group(1))
        start_month = int(match_paren.group(1))
        start_day = int(match_paren.group(2))
        try:
            dt = datetime(year, start_month, start_day)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _parse_xls(df: pd.DataFrame) -> Optional[dict]:
    """XLS DataFrameから1週分のデータを抽出"""
    date_str = _parse_date_from_xls(df)
    if not date_str:
        return None
    record = {"date": date_str}
    for col_name, row_candidates in ROW_POSITIONS.items():
        found = None
        for row_idx in row_candidates:
            if row_idx >= df.shape[0] or NET_COL >= df.shape[1]:
                continue
            val = df.iloc[row_idx, NET_COL]
            parsed = _parse_value(val)
            if parsed is not None:
                found = parsed
                break
        record[col_name] = found
    return record


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
                text("SELECT MAX(date) FROM jpx_investor_trading")
            ).fetchone()
            if row and row[0]:
                return row[0].strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"[JpxScheduler] Could not get latest DB date: {e}")
    return None


def fetch_latest_from_jpx() -> list[dict]:
    """JPX index pageから未取得のweekly XLSのみをダウンロード・パースしてレコードを返す。
    DBの最新日付以降のファイルだけを処理する（最新1件は常に再取得して更新）。
    """
    from bs4 import BeautifulSoup

    latest_db_date = _get_latest_date_in_db()
    logger.info(f"[JpxScheduler] Latest date in DB: {latest_db_date}")

    logger.info(f"[JpxScheduler] Fetching {JPX_INDEX_URL}")
    resp = requests.get(JPX_INDEX_URL, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        logger.error(f"[JpxScheduler] HTTP {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    xls_urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "stock_val_1_" in href and href.endswith(".xls"):
            fname = href.split("/")[-1]
            if "_m" not in fname and "_y" not in fname:
                full_url = JPX_BASE + href if href.startswith("/") else href
                xls_urls.append(full_url)

    logger.info(f"[JpxScheduler] Found {len(xls_urls)} weekly XLS links on page")

    # 新しいファイルから順に処理（最新3件のみダウンロード）
    # ファイル名の日付部分でソート（降順）してから最新N件に絞る
    xls_urls.sort(reverse=True)
    max_download = 3
    xls_urls = xls_urls[:max_download]
    logger.info(f"[JpxScheduler] Downloading latest {len(xls_urls)} XLS files")

    records = []
    for url in xls_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"[JpxScheduler] HTTP {resp.status_code}: {url}")
                continue
            df = pd.read_excel(io.BytesIO(resp.content), sheet_name="Tokyo & Nagoya", header=None)
            rec = _parse_xls(df)
            if rec:
                records.append(rec)
            else:
                logger.warning(f"[JpxScheduler] Failed to parse: {url}")
        except Exception as e:
            logger.warning(f"[JpxScheduler] Error: {url}: {e}")

    # DB最新日付より新しいレコードのみ返す（ただし最新日付と同日のレコードも含めて更新を許可）
    if latest_db_date and records:
        new_records = [r for r in records if r["date"] >= latest_db_date]
        logger.info(f"[JpxScheduler] {len(records)} parsed, {len(new_records)} are new/updated")
        return new_records

    return records


def save_to_db(records: list[dict]) -> int:
    """レコードをDBに保存 (UPSERT)。挿入/更新数を返す。"""
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
                    INSERT INTO jpx_investor_trading
                        (date, individuals, foreigners, trust_banks,
                         investment_trusts, business_corps, proprietary, source)
                    VALUES
                        (:date, :individuals, :foreigners, :trust_banks,
                         :investment_trusts, :business_corps, :proprietary, 'XLS')
                    ON CONFLICT (date) DO UPDATE SET
                        individuals = EXCLUDED.individuals,
                        foreigners = EXCLUDED.foreigners,
                        trust_banks = EXCLUDED.trust_banks,
                        investment_trusts = EXCLUDED.investment_trusts,
                        business_corps = EXCLUDED.business_corps,
                        proprietary = EXCLUDED.proprietary,
                        updated_at = NOW()
                """),
                rec,
            )
            if result.rowcount > 0:
                count += 1
        session.commit()

    return count


def clear_service_cache():
    """サービスのRedisキャッシュをクリアして次回リクエストでDB再読み込みを促す"""
    try:
        from backend.core.redis_client import redis_client
    except ImportError:
        from core.redis_client import redis_client

    redis_client.delete("market:jpx_investor_trading:data")
    logger.info("[JpxScheduler] Cleared Redis cache")


class JpxInvestorTradingScheduler:
    """投資部門別売買状況 週次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    async def _run(self):
        """JPXから最新XLSを取得しDBに保存"""
        try:
            logger.info("[JpxScheduler] Starting weekly update...")
            records = fetch_latest_from_jpx()
            if not records:
                logger.warning("[JpxScheduler] No records fetched")
                return

            count = save_to_db(records)
            logger.info(f"[JpxScheduler] Saved {count} records to DB")

            dates = sorted([r["date"] for r in records])
            logger.info(f"[JpxScheduler] Date range: {dates[0]} ~ {dates[-1]}")

            # キャッシュクリアして次回リクエストで最新データを返す
            clear_service_cache()

        except Exception as e:
            logger.error(f"[JpxScheduler] Error: {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """スケジューラーを開始
        - 毎週木曜 16:00 JST（JPX公開直後）
        - 毎週金曜 10:00 JST（リトライ）
        """
        self.scheduler.add_job(
            self._run,
            CronTrigger(day_of_week="thu", hour=16, minute=0, timezone=JST),
            id="jpx_investor_trading_weekly_thu",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(day_of_week="fri", hour=10, minute=0, timezone=JST),
            id="jpx_investor_trading_weekly_fri",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        logger.info("[JpxScheduler] Started (Thu 16:00 + Fri 10:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


jpx_investor_trading_scheduler = JpxInvestorTradingScheduler()
