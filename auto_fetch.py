"""
韓国半導体輸出 自動取得モジュール
===================================
毎月の最新レポートを自動取得してDBまたはJSONに保存する。

スタンドアロン実行:
    python auto_fetch.py                    # 最新取得してJSON保存
    python auto_fetch.py --db               # DB保存（要カスタマイズ）

APScheduler連携:
    from auto_fetch import register_jobs
    register_jobs(scheduler, save_func=your_db_save)

cron連携:
    # 毎月2日と15日に実行
    0 9 2 * * cd /path/to/scraper && python auto_fetch.py
    0 10 15 * * cd /path/to/scraper && python auto_fetch.py
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Optional

from scraper import (
    SemiconductorExportRecord,
    scrape_all,
    deduplicate_records,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 保存関数
# ---------------------------------------------------------------------------

async def save_to_json(
    records: list[SemiconductorExportRecord],
    filepath: str = "kr_semiconductor_latest.json",
):
    """JSONファイルに保存"""
    # 既存データがあれば読み込んでマージ
    existing = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            for d in data.get("data", []):
                existing.append(SemiconductorExportRecord(**d))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # マージ＆重複排除
    all_records = existing + records
    merged = deduplicate_records(all_records)

    output = {
        "indicator": "kr_semiconductor_exports",
        "unit": "USD billion",
        "source": "MOTIE ICT 수출입 동향",
        "updated_at": datetime.now().isoformat(),
        "total_months": len(merged),
        "data": [r.to_dict() for r in merged],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(merged)} records to {filepath} (new: {len(records)})")
    return merged


# ---------------------------------------------------------------------------
# 自動取得ジョブ
# ---------------------------------------------------------------------------

async def fetch_latest(
    save_func: Optional[Callable] = None,
) -> list[SemiconductorExportRecord]:
    """
    最新のレポートを取得して保存する。
    
    Returns:
        今回取得した新規レコードのリスト
    """
    logger.info("=== KR Semiconductor: fetching latest ===")

    trade_result, ict_result = await scrape_all()
    
    all_records = []
    
    if ict_result.records:
        logger.info(f"ICT report: {len(ict_result.records)} records from {ict_result.report_title}")
        all_records.extend(ict_result.records)
    else:
        logger.warning(f"ICT report: no data. {ict_result.errors}")

    if trade_result.records:
        logger.info(f"Trade report: {len(trade_result.records)} records from {trade_result.report_title}")
        all_records.extend(trade_result.records)
    else:
        logger.warning(f"Trade report: no data. {trade_result.errors}")

    merged = deduplicate_records(all_records)

    if merged:
        if save_func:
            await save_func(merged)
        else:
            await save_to_json(merged)
        
        logger.info(
            f"Latest: {merged[-1].ref_month} "
            f"${merged[-1].value_usd_billion}B "
            f"(YoY {merged[-1].yoy_pct}%)"
        )
    else:
        logger.error("No records fetched")

    return merged


# ---------------------------------------------------------------------------
# APScheduler 連携
# ---------------------------------------------------------------------------

def _run_async(coro):
    """sync ラッパー（APScheduler は sync 関数を期待）"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def register_jobs(scheduler, save_func=None):
    """
    APScheduler にジョブを登録する。

    ICTレポートは毎月12〜15日、수출입 동향は毎月1日に公開。
    両方をカバーするため、月2回実行する。
    
    Usage:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        register_jobs(scheduler, save_func=my_db_save)
        scheduler.start()
    """
    # 月初（수출입 동향 公開後）: 毎月2〜5日
    scheduler.add_job(
        func=lambda: _run_async(fetch_latest(save_func)),
        trigger="cron",
        day="2-5",
        hour=9,
        minute=0,
        timezone="Asia/Seoul",
        id="kr_semi_monthly_early",
        name="KR Semiconductor - Monthly (Trade Report)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # 月中旬（ICTレポート公開後）: 毎月13〜18日
    scheduler.add_job(
        func=lambda: _run_async(fetch_latest(save_func)),
        trigger="cron",
        day="13-18",
        hour=10,
        minute=0,
        timezone="Asia/Seoul",
        id="kr_semi_monthly_mid",
        name="KR Semiconductor - Monthly (ICT Report)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    logger.info("Registered KR semiconductor jobs:")
    logger.info("  - Early month:  2nd-5th, 09:00 KST")
    logger.info("  - Mid month:    13th-18th, 10:00 KST")


# ---------------------------------------------------------------------------
# DB スキーマ（参考）
# ---------------------------------------------------------------------------

DB_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kr_semiconductor_exports (
    id                BIGSERIAL PRIMARY KEY,
    ref_month         VARCHAR(7)    NOT NULL UNIQUE,  -- "2025-03"
    value_usd_billion NUMERIC(10,3),                   -- 10億ドル
    yoy_pct           NUMERIC(8,2),                    -- 前年同月比 %
    source_report     VARCHAR(20)   NOT NULL,           -- "ICT" / "TRADE"
    published_at      VARCHAR(20),
    source_url        TEXT,
    raw_text          TEXT,
    created_at        TIMESTAMPTZ   DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kr_semi_month
    ON kr_semiconductor_exports (ref_month);
"""

# ---------------------------------------------------------------------------
# FastAPI エンドポイント例（参考）
# ---------------------------------------------------------------------------

FASTAPI_EXAMPLE = '''
@router.get("/api/v1/kr/semiconductor-exports")
async def get_kr_semiconductor_exports(months: int = 24):
    """韓国半導体輸出の月次時系列"""
    result = await db.execute(
        text("""
            SELECT ref_month, value_usd_billion, yoy_pct, source_report
            FROM kr_semiconductor_exports
            ORDER BY ref_month DESC LIMIT :months
        """), {"months": months}
    )
    return {"data": [dict(r) for r in reversed(result.fetchall())]}
'''


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 60)
    print("韓国半導体輸出 自動取得")
    print("=" * 60)

    records = await fetch_latest()

    if records:
        print(f"\n取得結果: {len(records)}件")
        for r in records:
            print(f"  {r.ref_month}: ${r.value_usd_billion}B (YoY {r.yoy_pct}%)")
        print(f"\n→ kr_semiconductor_latest.json に保存済み")
    else:
        print("取得失敗")


if __name__ == "__main__":
    asyncio.run(main())
