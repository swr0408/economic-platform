"""
Valuation サービス共通の健全性チェックユーティリティ

目的:
  yfinance が要求と異なるティッカーのデータ（例: ^GSPC を要求したのに ^VIX が返る）や、
  明らかに異常なスケールの値を返すことがある。これを検出せずにキャッシュへ保存すると、
  破損データが SWR で半永久的に配信され続ける（再取得は PE CSV の mtime 変化時のみのため）。

  そこで取得直後に値を検証し、異常を検出した場合は ValueError を送出する。
  呼び出し側（_build_data → get_data）はこれを捕捉して保存をスキップし、
  直前の正常なキャッシュ（Redis / ファイル）を維持する。
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def assert_expected_ticker(df: pd.DataFrame, expected: str) -> None:
    """yfinance が要求したティッカーのデータを返しているか検証する。

    yfinance は単一ティッカーでも MultiIndex 列（names=['Price','Ticker']）を返す。
    Ticker レベルに expected が含まれない場合は誤ティッカーとみなし中断する。
    単層列（旧バージョン等）でティッカーが判別できない場合は、値レンジ検証に委ねる。
    """
    if isinstance(df.columns, pd.MultiIndex):
        tickers = {str(t) for t in df.columns.get_level_values(-1)}
        if expected not in tickers:
            raise ValueError(
                f"yfinance returned wrong ticker(s) {sorted(tickers)}, "
                f"expected {expected!r} - refusing to cache"
            )


def assert_value_range(series: pd.Series, label: str, lo: float, hi: float) -> None:
    """系列の最新値が想定レンジ [lo, hi] 内かを検証する。

    誤ティッカー（指数のはずが VIX 等）や破損データを検出するための最終防衛線。
    範囲外なら ValueError を送出し、破損データのキャッシュを防ぐ。
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        raise ValueError(f"{label}: no valid numeric data - refusing to cache")
    last = float(s.iloc[-1])
    if not (lo <= last <= hi):
        raise ValueError(
            f"{label}: latest value {last} outside expected range [{lo}, {hi}] "
            f"- likely wrong ticker or corrupt data; refusing to cache"
        )
