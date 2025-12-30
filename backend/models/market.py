"""
市場データモデル
PostgreSQL + TimescaleDB用

テーブル:
- market_symbols: 銘柄マスタ
- market_daily_data: 日足データ（TimescaleDBハイパーテーブル）
- market_intraday_data: 分足データ（TimescaleDBハイパーテーブル）
- indicator_releases: 指標発表日時マスタ
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Float, Date, DateTime, Boolean,
    Numeric, Index, UniqueConstraint, ForeignKey, Text,
    BigInteger
)
from sqlalchemy.orm import relationship
from core.database import Base


class MarketSymbol(Base):
    """銘柄マスタ"""
    __tablename__ = "market_symbols"

    id = Column(String(50), primary_key=True)  # usdjpy, sp500, etc.
    ticker = Column(String(50), nullable=False)  # yfinanceのティッカー
    name = Column(String(100), nullable=False)  # 日本語名
    name_en = Column(String(100), nullable=False)  # 英語名
    category = Column(String(50), nullable=False)  # forex, index, commodity, bond
    sub_category = Column(String(50), nullable=True)  # forex_usd, index_us, etc.
    is_active = Column(Boolean, default=True)  # 有効フラグ

    # 計算値用（例: gold_jpy = gold * usdjpy）
    is_calculated = Column(Boolean, default=False)
    base_symbol_id = Column(String(50), nullable=True)  # 計算元銘柄
    fx_symbol_id = Column(String(50), nullable=True)  # 為替銘柄
    operation = Column(String(20), nullable=True)  # multiply, divide

    # メタデータ
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーション
    daily_data = relationship("MarketDailyData", back_populates="symbol", lazy="dynamic")


class MarketDailyData(Base):
    """
    日足データ
    TimescaleDBのハイパーテーブルとして作成
    """
    __tablename__ = "market_daily_data"

    # 複合主キー: symbol_id + date
    symbol_id = Column(String(50), ForeignKey("market_symbols.id"), primary_key=True)
    date = Column(Date, primary_key=True)

    # OHLCデータ
    open = Column(Numeric(18, 6), nullable=True)
    high = Column(Numeric(18, 6), nullable=True)
    low = Column(Numeric(18, 6), nullable=True)
    close = Column(Numeric(18, 6), nullable=True)
    volume = Column(BigInteger, nullable=True)

    # メタデータ
    source = Column(String(50), default="yfinance")  # データソース
    created_at = Column(DateTime, default=datetime.utcnow)

    # リレーション
    symbol = relationship("MarketSymbol", back_populates="daily_data")

    __table_args__ = (
        Index("ix_market_daily_symbol_date", "symbol_id", "date"),
    )


class MarketIntradayData(Base):
    """
    分足データ（1分足、5分足）
    TimescaleDBのハイパーテーブルとして作成
    圧縮ポリシー適用推奨
    """
    __tablename__ = "market_intraday_data"

    # 複合主キー: symbol_id + timestamp + interval
    symbol_id = Column(String(50), ForeignKey("market_symbols.id"), primary_key=True)
    timestamp = Column(DateTime, primary_key=True)  # UTC
    interval = Column(String(10), primary_key=True)  # "1m", "5m"

    # OHLCデータ
    open = Column(Numeric(18, 6), nullable=True)
    high = Column(Numeric(18, 6), nullable=True)
    low = Column(Numeric(18, 6), nullable=True)
    close = Column(Numeric(18, 6), nullable=True)
    volume = Column(BigInteger, nullable=True)

    # メタデータ
    source = Column(String(50), default="yfinance")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_market_intraday_symbol_ts", "symbol_id", "timestamp", "interval"),
    )


class IndicatorRelease(Base):
    """
    指標発表日時マスタ
    経済指標の発表スケジュールを管理
    """
    __tablename__ = "indicator_releases"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 指標情報
    indicator_id = Column(String(100), nullable=False)  # ism_manufacturing, nonfarm_payrolls, etc.
    indicator_name = Column(String(200), nullable=False)  # ISM製造業景況指数
    country = Column(String(50), nullable=False)  # usa, japan, etc.

    # 発表日時（UTC）
    release_datetime = Column(DateTime, nullable=False)

    # 発表値（取得後に更新）
    actual_value = Column(Numeric(18, 4), nullable=True)
    forecast_value = Column(Numeric(18, 4), nullable=True)
    previous_value = Column(Numeric(18, 4), nullable=True)

    # メタデータ
    source = Column(String(100), nullable=True)  # investing.com, etc.
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_indicator_releases_datetime", "release_datetime"),
        Index("ix_indicator_releases_indicator", "indicator_id", "release_datetime"),
        UniqueConstraint("indicator_id", "release_datetime", name="uq_indicator_release"),
    )


class MarketDataUpdateLog(Base):
    """
    市場データ更新ログ
    スケジューラーの実行履歴を記録
    """
    __tablename__ = "market_data_update_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    symbol_id = Column(String(50), nullable=True)  # NULL = 全銘柄
    data_type = Column(String(20), nullable=False)  # daily, intraday_1m, intraday_5m

    # 実行結果
    status = Column(String(20), nullable=False)  # success, failed, partial
    records_updated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # 実行時間
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_update_logs_started", "started_at"),
    )
