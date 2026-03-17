"""
韓国半導体輸出 スケジューラー連携
==================================
既存の APScheduler ベースの自動取得基盤に組み込むためのモジュール。

使い方:
    from scheduler import register_kr_semiconductor_jobs
    
    # APScheduler の scheduler インスタンスに登録
    register_kr_semiconductor_jobs(scheduler, db_save_func=your_save_func)
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from scraper import (
    SemiconductorExportRecord,
    ScrapeResult,
    scrape_latest_trade_report,
    scrape_latest_ict_report,
    deduplicate_records,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB 保存インターフェース
# ---------------------------------------------------------------------------

async def default_save_func(records: list[SemiconductorExportRecord], source: str):
    """
    デフォルトの保存関数（JSON ファイル出力）。
    実運用では FastAPI + PostgreSQL/TimescaleDB への INSERT に差し替える。
    
    実装例:
        async def save_to_db(records, source):
            async with db.acquire() as conn:
                for r in records:
                    await conn.execute('''
                        INSERT INTO kr_semiconductor_exports 
                            (ref_month, value_usd_billion, yoy_pct, 
                             source_report, published_at, source_url, raw_text)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (ref_month) DO UPDATE SET
                            value_usd_billion = EXCLUDED.value_usd_billion,
                            yoy_pct = EXCLUDED.yoy_pct,
                            source_report = EXCLUDED.source_report,
                            published_at = EXCLUDED.published_at,
                            updated_at = NOW()
                    ''', r.ref_month, r.value_usd_billion, r.yoy_pct,
                         r.source_report, r.published_at, r.source_url, r.raw_text)
    """
    import json
    output = {
        "saved_at": datetime.now().isoformat(),
        "source": source,
        "records": [r.to_dict() for r in records],
    }
    filename = f"kr_semi_latest_{source.lower()}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(records)} records to {filename}")


# ---------------------------------------------------------------------------
# ジョブ関数
# ---------------------------------------------------------------------------

async def job_fetch_trade_report(
    save_func: Optional[Callable] = None,
):
    """
    毎月初の「수출입 동향」から半導体速報値を取得するジョブ。
    
    スケジュール: 毎月 2〜5日、1日1回リトライ
    """
    save = save_func or default_save_func
    
    logger.info("=== Job: Fetch MOTIE Trade Report (Semiconductor) ===")
    
    try:
        result = await scrape_latest_trade_report()
        
        if result.records:
            await save(result.records, "TRADE")
            logger.info(
                f"Trade report: {len(result.records)} records saved. "
                f"Latest: {result.records[0].ref_month} "
                f"${result.records[0].value_usd_billion}B"
            )
        else:
            logger.warning(f"Trade report: no records. Errors: {result.errors}")
            
    except Exception as e:
        logger.exception(f"Trade report job failed: {e}")


async def job_fetch_ict_report(
    save_func: Optional[Callable] = None,
):
    """
    毎月中旬の「ICT 수출입 동향」から半導体詳細データ（13ヶ月分）を取得するジョブ。
    
    スケジュール: 毎月 13〜18日、1日1回リトライ
    """
    save = save_func or default_save_func
    
    logger.info("=== Job: Fetch MOTIE ICT Report (Semiconductor Detail) ===")
    
    try:
        result = await scrape_latest_ict_report()
        
        if result.records:
            # ICT レポートは13ヶ月分含むので重複排除
            merged = deduplicate_records(result.records)
            await save(merged, "ICT")
            logger.info(
                f"ICT report: {len(merged)} records saved. "
                f"Range: {merged[0].ref_month} ~ {merged[-1].ref_month}"
            )
        else:
            logger.warning(f"ICT report: no records. Errors: {result.errors}")
            
    except Exception as e:
        logger.exception(f"ICT report job failed: {e}")


def _run_async(coro):
    """sync ラッパー（APScheduler は sync 関数を期待するため）"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# APScheduler 登録
# ---------------------------------------------------------------------------

def register_kr_semiconductor_jobs(scheduler, db_save_func=None):
    """
    APScheduler にジョブを登録する。
    
    Args:
        scheduler: APScheduler の BackgroundScheduler or AsyncIOScheduler
        db_save_func: async def save(records, source) 形式のDB保存関数
    
    Usage:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        register_kr_semiconductor_jobs(scheduler, db_save_func=my_save)
        scheduler.start()
    """
    
    # 1. 수출입 동향（速報）: 毎月2日〜5日の朝9時（KST）にリトライ
    #    MOTIE は毎月1日に公開するが、遅れる場合があるため2日から開始
    scheduler.add_job(
        func=lambda: _run_async(job_fetch_trade_report(db_save_func)),
        trigger="cron",
        day="2-5",
        hour=9,
        minute=0,
        timezone="Asia/Seoul",
        id="kr_semi_trade_report",
        name="KR Semiconductor - Trade Report (Monthly Headline)",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    
    # 2. ICT 수출입 동향（詳細）: 毎月13日〜18日の朝10時（KST）にリトライ
    #    通常12〜15日に公開
    scheduler.add_job(
        func=lambda: _run_async(job_fetch_ict_report(db_save_func)),
        trigger="cron",
        day="13-18",
        hour=10,
        minute=0,
        timezone="Asia/Seoul",
        id="kr_semi_ict_report",
        name="KR Semiconductor - ICT Report (Monthly Detail)",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    
    logger.info("Registered KR semiconductor export jobs:")
    logger.info("  - Trade Report: 2nd-5th of each month, 09:00 KST")
    logger.info("  - ICT Report:   13th-18th of each month, 10:00 KST")


# ---------------------------------------------------------------------------
# DB スキーマ（参考）
# ---------------------------------------------------------------------------

DB_SCHEMA_SQL = """
-- PostgreSQL / TimescaleDB

CREATE TABLE IF NOT EXISTS kr_semiconductor_exports (
    id              BIGSERIAL PRIMARY KEY,
    ref_month       VARCHAR(7)   NOT NULL,   -- "2025-03"
    value_usd_billion NUMERIC(10,3),          -- 10億ドル単位
    yoy_pct         NUMERIC(8,2),             -- 前年同月比 %
    source_report   VARCHAR(20)  NOT NULL,    -- "TRADE", "ICT", "VERIFIED_SEED"
    published_at    VARCHAR(20),              -- 公開日
    source_url      TEXT,
    raw_text        TEXT,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW(),
    
    CONSTRAINT uq_kr_semi_month UNIQUE (ref_month)
);

-- ref_month でのクエリを高速化
CREATE INDEX IF NOT EXISTS idx_kr_semi_ref_month 
    ON kr_semiconductor_exports (ref_month);

-- TimescaleDB を使う場合（オプション）
-- ref_month を date に変換して hypertable にすることも可能
-- SELECT create_hypertable('kr_semiconductor_exports', 'created_at', if_not_exists => TRUE);

-- 年間合計用テーブル（オプション）
CREATE TABLE IF NOT EXISTS kr_semiconductor_annual (
    year            INTEGER      PRIMARY KEY,
    value_usd_billion NUMERIC(10,3),
    yoy_pct         NUMERIC(8,2),
    source          VARCHAR(50),
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);
"""


# ---------------------------------------------------------------------------
# FastAPI エンドポイント（参考）
# ---------------------------------------------------------------------------

FASTAPI_ENDPOINT_EXAMPLE = '''
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/indicators/kr", tags=["kr-indicators"])

@router.get("/semiconductor-exports")
async def get_kr_semiconductor_exports(
    months: int = 24,
    db: AsyncSession = Depends(get_db),
):
    """韓国半導体輸出の月次時系列を返す"""
    result = await db.execute(
        text("""
            SELECT ref_month, value_usd_billion, yoy_pct, 
                   source_report, published_at
            FROM kr_semiconductor_exports
            WHERE ref_month != '____-00'
            ORDER BY ref_month DESC
            LIMIT :months
        """),
        {"months": months},
    )
    rows = result.fetchall()
    return {
        "indicator": "kr_semiconductor_exports",
        "country": "KR",
        "unit": "USD billion",
        "frequency": "monthly",
        "source": "MOTIE/MSIT",
        "data": [
            {
                "ref_month": r.ref_month,
                "value": float(r.value_usd_billion) if r.value_usd_billion else None,
                "yoy_pct": float(r.yoy_pct) if r.yoy_pct else None,
                "source": r.source_report,
            }
            for r in reversed(rows)
        ],
    }

@router.get("/semiconductor-exports/latest")
async def get_kr_semiconductor_latest(
    db: AsyncSession = Depends(get_db),
):
    """最新の韓国半導体輸出データ"""
    result = await db.execute(
        text("""
            SELECT ref_month, value_usd_billion, yoy_pct, 
                   source_report, published_at, updated_at
            FROM kr_semiconductor_exports
            WHERE ref_month != '____-00'
            ORDER BY ref_month DESC
            LIMIT 1
        """)
    )
    row = result.fetchone()
    if not row:
        return {"error": "No data available"}
    return {
        "ref_month": row.ref_month,
        "value_usd_billion": float(row.value_usd_billion),
        "yoy_pct": float(row.yoy_pct) if row.yoy_pct else None,
        "source": row.source_report,
        "published_at": row.published_at,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
'''


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    print("=== Manual Test: Run both jobs ===")
    _run_async(job_fetch_trade_report())
    _run_async(job_fetch_ict_report())
