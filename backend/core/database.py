"""
データベース接続設定
PostgreSQL + TimescaleDB
"""
import logging
import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from typing import Generator
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# 環境変数からDB URLを取得。
# 未設定時は docker-compose / .env と整合する canonical 値にフォールバックし、警告を出す。
# (過去に "economic_db" を指す古いフォールバック値が使われ、container側 "economic_platform" と
#  別DBに書き込んでしまった事象があったため、両者を統一)
_DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/economic_platform"
DATABASE_URL = os.getenv("DATABASE_URL") or _DEFAULT_DATABASE_URL
if not os.getenv("DATABASE_URL"):
    logger.warning(
        "DATABASE_URL is not set; falling back to %s. "
        "Load .env or set DATABASE_URL explicitly to silence this warning.",
        _DEFAULT_DATABASE_URL,
    )

# SQLAlchemy Engine（同期版 - シンプル）
#
# プールサイズについて:
#   再起動直後の起動時キャッチアップ + ダッシュボード load_all（1ダッシュボードで
#   最大 25 スレッドが並列に DB へアクセス）が一斉に走ると、旧設定 (pool_size=10 +
#   max_overflow=20 = 最大30) を食い尽くし、ログイン等の対話的リクエストの get_db が
#   空き接続を pool_timeout(既定30秒) 待って 30秒タイムアウトする事象があった。
#   Postgres 側 max_connections=100・シングルワーカー・アイドル時 ~14 接続のため、
#   プールを 50 まで広げてもヘッドルームは十分（raw psycopg2 接続 + 予約分を考慮しても安全）。
#   → バックグラウンド更新で埋まっても対話的リクエスト用の空きが残る。
#   接続「数」を増やすだけで取得並列度＝データ更新速度には影響しない（取りこぼし/更新遅延なし）。
# pool_timeout=20: 万一プールが枯渇しても、フロントの 30秒タイムアウト手前で素早く失敗させ、
#   30秒丸ごとハングするのを防ぐ（フロントは一時エラーで誤ログアウトしないよう修正済み）。
# pool_use_lifo=True: バースト後に接続を使い回し、実際に開く接続数を抑えてプールを温存する。
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_timeout=20,
    pool_use_lifo=True,
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


@contextmanager
def get_db_connection():
    """
    psycopg2の生接続を取得するコンテキストマネージャ

    calendar_repository等で使用
    """
    # DATABASE_URLからpsycopg2用のパラメータを解析
    from urllib.parse import urlparse
    parsed = urlparse(DATABASE_URL)

    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=parsed.path.lstrip('/'),
        user=parsed.username,
        password=parsed.password,
    )
    try:
        yield conn
    finally:
        conn.close()
