"""
上海コンテナ運賃指数 (SCFI/CCFI) CSV → DB インポート & キャッシュ無効化

CSV: backend/data/csv_import/コンテナ運賃指数.csv
DB:  nbs_monthly_data テーブル (indicator='scfi' / 'ccfi')

Usage:
    python backend/scripts/import_container_freight_index.py
"""

import importlib
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.redis_client import redis_client


SERVICE_CACHE_KEY = "global:china_shanghai_container_freight_index:data"
DASHBOARD_CACHE_KEYS = [
    "global:economy:dashboard:v1",
    "global:economy:dashboard:v1:light",
    "global:economy:dashboard:v1:heavy",
]


def main() -> None:
    mod = importlib.import_module(
        "services.global.china_shanghai_container_freight_index_service"
    )

    print("=" * 60)
    print("Step 1: CSV → DB import")
    print("=" * 60)
    total = mod.import_csv_to_db()
    print(f"  upserted records: {total}")

    print()
    print("=" * 60)
    print("Step 2: Invalidate caches")
    print("=" * 60)
    for key in [SERVICE_CACHE_KEY, *DASHBOARD_CACHE_KEYS]:
        deleted = redis_client.delete(key)
        print(f"  {key}: {'deleted' if deleted else 'not found'}")

    print()
    print("Done. Reload /country/global/economy#container-freight-index to verify.")


if __name__ == "__main__":
    main()
