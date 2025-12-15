"""
データベース接続設定
PostgreSQL + TimescaleDB
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from typing import Generator

# 環境変数からDB URLを取得
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://economic:economic@localhost:5432/economic_db"
)

# SQLAlchemy Engine（同期版 - シンプル）
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# セッションファクトリ
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ベースクラス
Base = declarative_base()


def get_db() -> Generator:
    """データベースセッションを取得（FastAPI Dependency用）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    """データベース接続テスト"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection successful!")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
