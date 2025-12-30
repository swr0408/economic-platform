"""
econalpha_name更新スクリプト
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

def alter_constraints():
    """テーブルの制約を変更（NOT NULLを削除）"""
    with get_db_connection() as conn:
        conn.autocommit = True  # DDLはautocommitで実行
        with conn.cursor() as cur:
            try:
                cur.execute("ALTER TABLE indicator_event_mapping ALTER COLUMN econalpha_id DROP NOT NULL")
                print("econalpha_id: NOT NULL制約を削除")
            except Exception as e:
                print(f"econalpha_id制約変更: {e}")

            try:
                cur.execute("ALTER TABLE indicator_event_mapping ALTER COLUMN econalpha_name DROP NOT NULL")
                print("econalpha_name: NOT NULL制約を削除")
            except Exception as e:
                print(f"econalpha_name制約変更: {e}")

            # UNIQUE制約も変更（NULLを許可するため削除して再作成）
            try:
                cur.execute("ALTER TABLE indicator_event_mapping DROP CONSTRAINT IF EXISTS indicator_event_mapping_econalpha_id_key")
                print("econalpha_id: UNIQUE制約を削除")
            except Exception as e:
                print(f"UNIQUE制約削除: {e}")

def run_update():
    """update_indicator_names.sqlを実行"""
    sql_path = Path(__file__).parent / "update_indicator_names.sql"

    with open(sql_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # ALTERステートメントを除外（既に上で実行済み）
    # セミコロンで分割して各ステートメントを実行
    statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--') and not 'ALTER TABLE' in s.upper()]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            success_count = 0
            error_count = 0

            for i, stmt in enumerate(statements):
                if not stmt or stmt.startswith('--'):
                    continue
                try:
                    cur.execute(stmt)
                    if stmt.strip().upper().startswith('UPDATE'):
                        success_count += cur.rowcount
                    elif stmt.strip().upper().startswith('SELECT'):
                        # 結果を表示
                        rows = cur.fetchall()
                        columns = [desc[0] for desc in cur.description]
                        print("\n=== 更新結果 ===")
                        print(" | ".join(columns))
                        print("-" * 60)
                        for row in rows:
                            print(" | ".join(str(v) for v in row))
                except Exception as e:
                    error_count += 1
                    print(f"Error executing statement {i}: {e}")
                    print(f"Statement: {stmt[:100]}...")

            conn.commit()
            print(f"\n完了: {success_count}件更新, {error_count}件エラー")

if __name__ == "__main__":
    print("Starting indicator names update...")
    print("\n1. テーブル制約を変更...")
    alter_constraints()
    print("\n2. データを更新...")
    run_update()
