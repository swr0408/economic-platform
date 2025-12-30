"""
FMP経済カレンダー バックフィル実行スクリプト
"""
import os
import sys
from pathlib import Path

# プロジェクトルートのパスを追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# .envを読み込む
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from backend.services.calendar.calendar_scheduler import calendar_scheduler

if __name__ == "__main__":
    print("Starting FMP calendar backfill (1 year)...")
    try:
        result = calendar_scheduler.backfill(days=365)
        print("\n=== Backfill Results ===")
        print(f"Total events fetched: {result.get('total_events', 'N/A')}")
        print(f"Filtered events: {result.get('filtered_events', 'N/A')}")
        print(f"Upserted to DB: {result.get('upserted_count', 'N/A')}")
        print(f"Duration: {result.get('duration_seconds', 'N/A'):.2f}s")
        print(f"Date range: {result.get('start_date')} to {result.get('end_date')}")
        print("========================")
    except Exception as e:
        print(f"Error during backfill: {e}")
        import traceback
        traceback.print_exc()
