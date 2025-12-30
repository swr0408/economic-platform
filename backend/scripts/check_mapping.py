"""
マッピング確認スクリプト
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

from backend.core.database import get_db_connection

with get_db_connection() as conn:
    with conn.cursor() as cur:
        # 国別の件数
        cur.execute('''
            SELECT
                country,
                COUNT(*) as total,
                COUNT(econalpha_id) as with_frontend_id,
                COUNT(*) - COUNT(econalpha_id) as without_frontend_id
            FROM indicator_event_mapping
            GROUP BY country
            ORDER BY country
        ''')
        rows = cur.fetchall()
        print('=== 国別マッピング数 ===')
        print(f'{"国":<5} | {"合計":<5} | {"フロントID有":<12} | {"フロントID無":<12}')
        print('-' * 50)
        for row in rows:
            print(f'{row[0]:<5} | {row[1]:<5} | {row[2]:<12} | {row[3]:<12}')

        # フロントエンドID有りのサンプル
        print()
        print('=== フロントエンドID有り ===')
        cur.execute('''
            SELECT econalpha_id, econalpha_name, country
            FROM indicator_event_mapping
            WHERE econalpha_id IS NOT NULL
            ORDER BY country, econalpha_id
        ''')
        for row in cur.fetchall():
            print(f'{row[0]:<30} | {row[1]:<30} | {row[2]}')
