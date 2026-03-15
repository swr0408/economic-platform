"""
東証プライム騰落レシオの初期データを構築するスクリプト

J-Quants API (Free plan: 5 req/min) のレートリミットに配慮し、
12-13秒間隔でAPIを呼び出す。

初回実行時は2年分のデータ構築に 3-4時間 かかる。
以降は差分のみ取得するため短時間で完了。

Usage:
    cd backend
    python scripts/import_advance_decline_ratio.py
"""
import sys
import os
import time
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

from services.market.advance_decline_ratio_service import advance_decline_ratio_service

if __name__ == "__main__":
    print("=" * 60)
    print("東証プライム 騰落レシオ データ構築")
    print("=" * 60)
    print()
    print("J-Quants Free plan rate limit: 5 req/min")
    print("初回実行時は 3-4時間 かかります。")
    print("Ctrl+C で中断しても、次回は続きから再開します。")
    print()

    start = time.time()
    try:
        result = advance_decline_ratio_service.get_data(force_refresh=True)
        elapsed = time.time() - start

        print()
        print("=" * 60)
        print(f"完了: {elapsed/60:.1f} 分")
        print(f"ソース: {result.get('source')}")
        print(f"データ件数: {len(result.get('data', []))}")

        if result.get("latest"):
            lat = result["latest"]
            print(f"最新日付: {lat.get('date')}")
            print(f"騰落レシオ: {lat.get('ratio')}%")
            print(f"上昇: {lat.get('advances')} / 下落: {lat.get('declines')} / 変わらず: {lat.get('unchanged')}")
        print("=" * 60)
    except KeyboardInterrupt:
        print("\n中断しました。次回は続きから再開します。")
    except Exception as e:
        print(f"\nエラー: {e}")
        raise
