from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event
from contextlib import asynccontextmanager
from backend.config import settings

# SQLAlchemy Engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # 接続確認
    pool_recycle=3600,   # 1時間で接続リサイクル
)

# Session Factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base Model
Base = declarative_base()

# Dependency
async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# データベース初期化
async def init_db():
    async with engine.begin() as conn:
        # TimescaleDB拡張を有効化
        await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
        
        # テーブル作成
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database initialized successfully!")

# 接続テスト
async def test_connection():
    try:
        async with async_session_maker() as session:
            result = await session.execute("SELECT version();")
            version = result.scalar()
            print(f"Database connected: {version}")
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
