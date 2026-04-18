"""
金ETF保有残高 日次スケジューラー

SPDR Gold Shares API からExcelをダウンロードし、
DB未登録の新しいデータを取得・登録する。

毎日 JST 08:00 にSPDR APIからExcelを取得し差分をDBにUPSERT。
リトライ: JST 12:00。
"""
import io
import re
import logging
from datetime import datetime, date, timedelta
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

SPDR_API_URL = (
    "https://api.spdrgoldshares.com/api/v1/historical-archive"
    "?product=1326&exchange=TSE&lang=ja"
)
SHEET_NAME = "JP 1326 Historical Archive"


def _find_column(df: pd.DataFrame, patterns: list[str]) -> str:
    for pat in patterns:
        rgx = re.compile(pat, re.I)
        for col in df.columns:
            if rgx.search(str(col)):
                return col
    raise ValueError(f"Column not found: {patterns}")


def _parse_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("\u2212", "-", regex=False)
        .str.replace("\u2013", "-", regex=False)
        .str.strip(),
        errors="coerce",
    )


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
                text("SELECT MAX(date) FROM gold_etf_holdings")
            ).fetchone()
            if row and row[0]:
                return row[0].strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"[GoldEtfScheduler] Could not get latest DB date: {e}")
    return None


def fetch_latest_from_spdr() -> list[dict]:
    """SPDR API からExcelをダウンロード・パースし、DB未登録のレコードを返す。"""
    import yfinance as yf

    latest_db_date = _get_latest_date_in_db()
    logger.info(f"[GoldEtfScheduler] Latest date in DB: {latest_db_date}")

    logger.info(f"[GoldEtfScheduler] Downloading SPDR Excel...")
    resp = requests.get(SPDR_API_URL, headers=HEADERS, timeout=60)
    if resp.status_code != 200:
        logger.error(f"[GoldEtfScheduler] HTTP {resp.status_code}")
        return []

    # ヘッダー行自動検出
    tmp = pd.read_excel(
        io.BytesIO(resp.content), sheet_name=SHEET_NAME, header=None, engine="openpyxl"
    )
    header_row = tmp[
        tmp.iloc[:, 0].astype(str).str.contains(r"^(?:Date|日付)$", case=False, na=False)
    ].index[0]

    df = pd.read_excel(
        io.BytesIO(resp.content),
        sheet_name=SHEET_NAME,
        header=header_row,
        engine="openpyxl",
    )
    df.columns = (
        df.columns.astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.replace("\u3000", " ")
        .str.strip()
    )

    # 休業日行を除外
    first_col = df.columns[0]
    mask = df[first_col].astype(str).str.contains("Holiday|休場|休業", na=False)
    df = df[~mask].copy()

    # 列を検索
    date_col = _find_column(df, [r"^日付$", r"^Date$"])
    ton_col = _find_column(df, [r"金保有量.*トン", r"ton"])
    nav_col = _find_column(df, [r"信託総純資産額", r"Net Asset Value"])
    close_usd_col = _find_column(df, [r"1326.*終値.*ドル", r"1326.*Close.*USD"])
    close_jpy_col = _find_column(df, [r"1326.*終値.*円", r"1326.*Close.*JPY"])

    parsed = pd.DataFrame()
    parsed["date"] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    parsed["holdings_ton"] = _parse_numeric(df[ton_col])
    parsed["nav_usd"] = _parse_numeric(df[nav_col])
    parsed["close_usd"] = _parse_numeric(df[close_usd_col])
    parsed["close_jpy"] = _parse_numeric(df[close_jpy_col])

    parsed = parsed[parsed["date"].notna()].sort_values("date").reset_index(drop=True)
    logger.info(f"[GoldEtfScheduler] Parsed {len(parsed)} total records")

    # DB最新日付以降のレコードのみ（同日も含めて更新許可）
    if latest_db_date:
        new_records = parsed[parsed["date"] >= pd.Timestamp(latest_db_date)]
        logger.info(f"[GoldEtfScheduler] {len(new_records)} new/updated records")
    else:
        new_records = parsed

    if new_records.empty:
        return []

    # yfinance GC=F で金価格を取得
    start_date = new_records["date"].min().strftime("%Y-%m-%d")
    gold_map: dict[str, float] = {}
    try:
        ticker = yf.Ticker("GC=F")
        hist = ticker.history(start=start_date, interval="1d")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None)
            for idx, row in hist.iterrows():
                gold_map[idx.strftime("%Y-%m-%d")] = round(float(row["Close"]), 2)
    except Exception as e:
        logger.warning(f"[GoldEtfScheduler] yfinance error: {e}")

    # レコード構築
    records = []
    for _, row in new_records.iterrows():
        date_str = row["date"].strftime("%Y-%m-%d")
        records.append({
            "date": date_str,
            "holdings_ton": None if pd.isna(row["holdings_ton"]) else float(row["holdings_ton"]),
            "nav_usd": None if pd.isna(row["nav_usd"]) else float(row["nav_usd"]),
            "close_usd": None if pd.isna(row["close_usd"]) else float(row["close_usd"]),
            "close_jpy": None if pd.isna(row["close_jpy"]) else float(row["close_jpy"]),
            "gold_price_usd": gold_map.get(date_str),
        })

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
                    INSERT INTO gold_etf_holdings
                        (date, holdings_ton, nav_usd, close_usd, close_jpy, gold_price_usd, source)
                    VALUES
                        (:date, :holdings_ton, :nav_usd, :close_usd, :close_jpy, :gold_price_usd, 'SPDR')
                    ON CONFLICT (date) DO UPDATE SET
                        holdings_ton = EXCLUDED.holdings_ton,
                        nav_usd = EXCLUDED.nav_usd,
                        close_usd = EXCLUDED.close_usd,
                        close_jpy = EXCLUDED.close_jpy,
                        gold_price_usd = COALESCE(EXCLUDED.gold_price_usd, gold_etf_holdings.gold_price_usd),
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

    redis_client.delete("market:gold_etf_holdings:data")
    logger.info("[GoldEtfScheduler] Cleared Redis cache")


class GoldEtfHoldingsScheduler:
    """金ETF保有残高 日次更新スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)

    async def _run(self):
        """SPDR APIから最新データを取得しDBに保存"""
        try:
            logger.info("[GoldEtfScheduler] Starting daily update...")
            records = fetch_latest_from_spdr()
            if not records:
                logger.warning("[GoldEtfScheduler] No new records")
                return

            count = save_to_db(records)
            logger.info(f"[GoldEtfScheduler] Saved {count} records to DB")

            dates = sorted([r["date"] for r in records])
            logger.info(f"[GoldEtfScheduler] Date range: {dates[0]} ~ {dates[-1]}")

            clear_service_cache()

        except Exception as e:
            logger.error(f"[GoldEtfScheduler] Error: {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """スケジューラーを開始
        - 毎日 08:00 JST（NY営業日終了後のデータ取得）
        - 毎日 12:00 JST（リトライ）
        - 起動時にDBが2日以上古ければ即時キャッチアップ
        """
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=8, minute=0, timezone=JST),
            id="gold_etf_holdings_daily_08",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self.scheduler.add_job(
            self._run,
            CronTrigger(hour=12, minute=0, timezone=JST),
            id="gold_etf_holdings_daily_12",
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
                logger.info(f"[GoldEtfScheduler] DB latest: {latest_db_str} ({age_days}d old)")
            except ValueError:
                pass
        if should_catchup:
            self.scheduler.add_job(
                self._run,
                "date",
                run_date=datetime.now(JST) + timedelta(seconds=30),
                id="gold_etf_holdings_startup_catchup",
                replace_existing=True,
            )
            logger.info("[GoldEtfScheduler] Startup catch-up scheduled (in 30s)")

        self.scheduler.start()
        logger.info("[GoldEtfScheduler] Started (08:00 + 12:00 JST)")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


gold_etf_holdings_scheduler = GoldEtfHoldingsScheduler()
