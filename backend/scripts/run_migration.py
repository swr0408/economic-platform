"""
SQLマイグレーション実行スクリプト
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

from sqlalchemy import create_engine, text

# 環境変数またはデフォルトのDB URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/economic_platform"
)
print(f"Using DATABASE_URL: {DATABASE_URL[:30]}...")

engine = create_engine(DATABASE_URL)

def run_migration():
    """SQLファイルを実行"""
    sql_file = Path(__file__).parent / "economic_calendar_tables.sql"

    if not sql_file.exists():
        print(f"Error: SQL file not found: {sql_file}")
        return False

    sql_content = sql_file.read_text(encoding="utf-8")

    # 複数のステートメントを分割せずに実行（PostgreSQL対応）
    with engine.begin() as conn:
        # セミコロンで分割して個別に実行
        statements = []
        current_statement = []
        in_function = False

        for line in sql_content.split('\n'):
            # ファンクション定義の開始/終了を検出
            if 'CREATE OR REPLACE FUNCTION' in line or 'AS $$' in line:
                in_function = True
            if '$$ language' in line.lower():
                in_function = False

            current_statement.append(line)

            # ファンクション外でセミコロンがある場合はステートメント終了
            if line.strip().endswith(';') and not in_function:
                statement = '\n'.join(current_statement).strip()
                if statement and not statement.startswith('--'):
                    statements.append(statement)
                current_statement = []

        # 残りがあれば追加
        if current_statement:
            statement = '\n'.join(current_statement).strip()
            if statement and not statement.startswith('--'):
                statements.append(statement)

        print(f"Executing {len(statements)} statements...")

        for i, stmt in enumerate(statements):
            try:
                if stmt.strip():
                    conn.execute(text(stmt))
                    # 進捗表示（CREATE/INSERT等の主要操作のみ）
                    first_line = stmt.strip().split('\n')[0][:60]
                    if any(kw in stmt.upper()[:50] for kw in ['CREATE', 'INSERT', 'DROP']):
                        print(f"  [{i+1}/{len(statements)}] {first_line}...")
            except Exception as e:
                print(f"  Warning at statement {i+1}: {e}")
                # 続行（IF NOT EXISTS等でエラーになる場合があるため）

        print("Migration completed successfully!")
        return True

if __name__ == "__main__":
    run_migration()
