"""
特定の指標確認スクリプト
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
        # ISM関連を確認
        print('=== ISM Manufacturing関連 ===')
        cur.execute('''
            SELECT id, econalpha_id, econalpha_name, fmp_event_patterns
            FROM indicator_event_mapping
            WHERE econalpha_id LIKE '%ism%' OR econalpha_id LIKE '%ISM%'
            ORDER BY econalpha_id
        ''')
        for row in cur.fetchall():
            print(f'ID: {row[0]} | econalpha_id: {row[1]} | name: {row[2]} | patterns: {row[3]}')

        # us_で始まるIDを確認（まだ変換されていないもの）
        print()
        print('=== us_で始まるID（未変換）===')
        cur.execute('''
            SELECT id, econalpha_id, econalpha_name
            FROM indicator_event_mapping
            WHERE econalpha_id LIKE 'us_%'
            ORDER BY econalpha_id
        ''')
        for row in cur.fetchall():
            print(f'ID: {row[0]} | econalpha_id: {row[1]} | name: {row[2]}')
