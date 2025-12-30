"""
完全な更新スクリプト
1. 既存データを削除
2. add_fmp_indicators.sqlを実行
3. add_fmp_indicators_part2.sqlを実行
4. update_indicator_names.sqlを実行
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

def execute_sql_file(filepath, conn):
    """SQLファイルを実行"""
    with open(filepath, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # セミコロンで分割
    statements = sql_content.split(';')

    with conn.cursor() as cur:
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt or stmt.startswith('--'):
                continue
            # コメント行のみの場合スキップ
            lines = [l for l in stmt.split('\n') if l.strip() and not l.strip().startswith('--')]
            if not lines:
                continue
            try:
                cur.execute(stmt)
            except Exception as e:
                print(f"Error: {e}")
                print(f"Statement: {stmt[:100]}...")
    conn.commit()

def alter_constraints():
    """テーブルの制約を変更（NOT NULLを削除）"""
    with get_db_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            try:
                cur.execute("ALTER TABLE indicator_event_mapping ALTER COLUMN econalpha_id DROP NOT NULL")
            except:
                pass
            try:
                cur.execute("ALTER TABLE indicator_event_mapping ALTER COLUMN econalpha_name DROP NOT NULL")
            except:
                pass
            try:
                cur.execute("ALTER TABLE indicator_event_mapping DROP CONSTRAINT IF EXISTS indicator_event_mapping_econalpha_id_key")
            except:
                pass

def main():
    script_dir = Path(__file__).parent

    print("1. テーブル制約を変更...")
    alter_constraints()

    print("2. add_fmp_indicators.sql を実行...")
    with get_db_connection() as conn:
        execute_sql_file(script_dir / "add_fmp_indicators.sql", conn)

    print("3. add_fmp_indicators_part2.sql を実行...")
    with get_db_connection() as conn:
        execute_sql_file(script_dir / "add_fmp_indicators_part2.sql", conn)

    print("4. update_indicator_names.sql を実行...")
    with get_db_connection() as conn:
        # ALTER文を除外したバージョンで実行
        with open(script_dir / "update_indicator_names.sql", 'r', encoding='utf-8') as f:
            sql_content = f.read()

        statements = sql_content.split(';')
        update_count = 0
        with conn.cursor() as cur:
            for stmt in statements:
                stmt = stmt.strip()
                if not stmt or stmt.startswith('--') or 'ALTER TABLE' in stmt.upper():
                    continue
                lines = [l for l in stmt.split('\n') if l.strip() and not l.strip().startswith('--')]
                if not lines:
                    continue
                try:
                    cur.execute(stmt)
                    if stmt.upper().startswith('UPDATE'):
                        update_count += cur.rowcount
                except Exception as e:
                    print(f"Error: {e}")
        conn.commit()
        print(f"   更新件数: {update_count}")

    print("\n5. 確認...")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT
                    country,
                    COUNT(*) as total,
                    COUNT(econalpha_id) as with_id
                FROM indicator_event_mapping
                GROUP BY country
                ORDER BY country
            ''')
            print("国 | 合計 | フロントID有")
            for row in cur.fetchall():
                print(f"{row[0]} | {row[1]} | {row[2]}")

if __name__ == "__main__":
    main()
