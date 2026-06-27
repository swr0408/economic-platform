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
# 接続数バジェット（Postgres max_connections=100 を全プロセスで分け合う）:
#   このバックエンドは main プロセスに加え、ダッシュボード更新用 ProcessPoolExecutor
#   (spawn) の **子プロセスが最大 3 つ常駐** する（services/dashboard/loaders/base.py）。
#   spawn 子は core.database を再 import して各自プールを生成するため、全プロセスの
#   pool_size 合計が max_connections を超えると idle 接続が累積し "too many clients" で
#   全 DB アクセスが落ちる（2026-06-18 に /saved 等が全滅した実障害の真因）。
#   QueuePool は pool_size 本を「常駐」保持し、max_overflow 分は返却時にクローズされる
#   （＝常駐 idle に積み上がるのは pool_size のみ）。これを踏まえた配分:
#     main : pool_size=20 + overflow=20 = 最大40（常駐20）
#     子   : configure_pool_for_worker() で pool_size=3 + overflow=12 = 最大15（常駐3）×3
#   → 常駐 idle ≈ 20 + 9 = 29、バースト最悪 ≈ 40 + 45 = 85 < 100（予約/Timescale分を残す）。
#   load_all は子プロセスへオフロード済みのため main の pool_size を 50→40 に絞っても
#   対話的リクエスト（ログイン等）用の空きは十分（過去のログイン30秒TOは main で
#   load_all を走らせていた事に起因し、現在は別プロセス）。env で上書き可能。
# pool_timeout=20: 万一プールが枯渇しても、フロントの 30秒タイムアウト手前で素早く失敗させ、
#   30秒丸ごとハングするのを防ぐ（フロントは一時エラーで誤ログアウトしないよう修正済み）。
# pool_use_lifo=True: バースト後に接続を使い回し、実際に開く接続数を抑えてプールを温存する。
# pool_pre_ping=True: stale 接続を返す前に検査し、再起動跨ぎ等の切断を自動回復する。


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _build_engine(pool_size: int, max_overflow: int):
    return create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=20,
        pool_use_lifo=True,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


engine = _build_engine(
    _int_env("DB_POOL_SIZE", 20),
    _int_env("DB_MAX_OVERFLOW", 20),
)

# セッションファクトリ
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def configure_pool_for_worker(pool_size: int = None, max_overflow: int = None) -> None:
    """子プロセス（ProcessPoolExecutor worker）用に接続プールを小さく作り直す。

    spawn 子プロセスは core.database を再 import して main と同じ大きさのプールを
    抱えてしまうため、main + 子3 で Postgres の max_connections(100) を食い潰す。
    子はバッチ用途なので常駐接続を絞った小プールへ再構成し、import 時に作られた
    プールは dispose して接続を残さない。ProcessPoolExecutor の initializer から呼ぶ。
    """
    global engine, SessionLocal
    ps = pool_size if pool_size is not None else _int_env("DB_WORKER_POOL_SIZE", 3)
    mo = max_overflow if max_overflow is not None else _int_env("DB_WORKER_MAX_OVERFLOW", 12)
    try:
        engine.dispose()
    except Exception:
        pass
    engine = _build_engine(ps, mo)
    SessionLocal.configure(bind=engine)

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
    psycopg2 の生接続を取得するコンテキストマネージャ（calendar_repository 等で使用）。

    生の psycopg2.connect ではなく **SQLAlchemy エンジンのプール経由** で取得する。
    これにより ORM セッションと生接続が同一プールを共有し、1 プロセスあたりの実接続数が
    必ず pool_size+max_overflow で頭打ちになる（上限なしの生接続で Postgres 全体を
    枯渇させない）。close() でプールへ返却され、pool_pre_ping/recycle が stale 接続を
    自動回復する。返るのは生の psycopg2 connection 互換オブジェクトなので
    cursor()/commit()/rollback() は従来どおり使える。
    """
    conn = engine.raw_connection()
    try:
        yield conn
    finally:
        # close() は実際には接続をプールへ返却する（SQLAlchemy が rollback でリセット）。
        conn.close()
