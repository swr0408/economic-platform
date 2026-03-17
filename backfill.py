"""
韓国半導体輸出 過去時系列バックフィル
======================================
MOTIEのICTレポート過去記事をページ送りで遡り、
インライン推移データから半導体輸出の月次時系列を構築する。

各ICTレポートには直近4ヶ月分の推移が含まれるため:
  - 1ページ(5記事) → 約10〜12ヶ月分
  - 2ページ(10記事) → 約18〜24ヶ月分
  - 3ページ(15記事) → 約24〜36ヶ月分

使い方:
    python backfill.py                # デフォルト2ページ（約2年分）
    python backfill.py --pages 4      # 4ページ分（約3年分）
    python backfill.py --output data/kr_semi_history.json
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime

from scraper import (
    SemiconductorExportRecord,
    ScrapeResult,
    scrape_ict_reports_backfill,
    scrape_all,
    deduplicate_records,
)

logger = logging.getLogger(__name__)


async def run_backfill(max_pages: int = 2, output_file: str = "kr_semiconductor_history.json"):
    """
    過去時系列バックフィルを実行する。
    
    1. 最新レポートから直近4ヶ月分を取得
    2. 過去ページを遡って時系列を拡張
    3. 重複排除して時系列順に保存
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    all_records: list[SemiconductorExportRecord] = []
    
    # --- Phase 1: 最新レポート ---
    print("=" * 60)
    print("Phase 1: 最新レポート取得")
    print("=" * 60)
    
    trade_result, ict_result = await scrape_all()
    
    if ict_result.records:
        print(f"  最新ICT: {ict_result.report_title}")
        print(f"  取得件数: {len(ict_result.records)}")
        for r in ict_result.records:
            print(f"    {r.ref_month}: ${r.value_usd_billion}B (YoY {r.yoy_pct}%)")
        all_records.extend(ict_result.records)
    else:
        print(f"  最新ICT: 取得失敗 {ict_result.errors}")
    
    if trade_result.records:
        print(f"  最新Trade: {trade_result.report_title}")
        print(f"  取得件数: {len(trade_result.records)}")
        all_records.extend(trade_result.records)
    
    # --- Phase 2: 過去ページバックフィル ---
    print(f"\n{'='*60}")
    print(f"Phase 2: 過去ページバックフィル（{max_pages}ページ）")
    print("=" * 60)
    
    backfill_results = await scrape_ict_reports_backfill(max_pages=max_pages)
    
    for sr in backfill_results:
        title_short = sr.report_title[:50] if sr.report_title else "?"
        if sr.records:
            print(f"  {title_short}: {len(sr.records)} records")
            for r in sr.records:
                print(f"    {r.ref_month}: ${r.value_usd_billion}B (YoY {r.yoy_pct}%)")
            all_records.extend(sr.records)
        else:
            print(f"  {title_short}: 0 records {sr.errors}")
    
    # --- Phase 3: 統合・重複排除 ---
    print(f"\n{'='*60}")
    print("Phase 3: 統合・重複排除")
    print("=" * 60)
    
    merged = deduplicate_records(all_records)
    
    print(f"\n  全{len(merged)}ヶ月分の時系列:")
    print(f"  {'─'*50}")
    for r in merged:
        print(f"  {r.ref_month}  ${r.value_usd_billion:>7.2f}B  YoY {r.yoy_pct:>+7.1f}%")
    
    if merged:
        print(f"\n  期間: {merged[0].ref_month} 〜 {merged[-1].ref_month}")
    
    # --- Phase 4: JSON保存 ---
    output = {
        "indicator": "kr_semiconductor_exports",
        "description": "韓国半導体輸出（MOTIE/MSIT ICTレポート）",
        "unit": "USD billion",
        "source": "MOTIE ICT 수출입 동향",
        "backfill_at": datetime.now().isoformat(),
        "total_months": len(merged),
        "date_range": {
            "start": merged[0].ref_month if merged else None,
            "end": merged[-1].ref_month if merged else None,
        },
        "data": [r.to_dict() for r in merged],
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n  → {output_file} に保存しました（{len(merged)}件）")
    return merged


def main():
    parser = argparse.ArgumentParser(description="韓国半導体輸出 過去時系列バックフィル")
    parser.add_argument("--pages", type=int, default=2, help="遡るページ数（デフォルト: 2、約2年分）")
    parser.add_argument("--output", type=str, default="kr_semiconductor_history.json", help="出力ファイル名")
    args = parser.parse_args()
    
    asyncio.run(run_backfill(max_pages=args.pages, output_file=args.output))


if __name__ == "__main__":
    main()
