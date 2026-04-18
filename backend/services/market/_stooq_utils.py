"""Stooq CSV API 共通ユーティリティ

Stooq は 2026年頃から CSV ダウンロード API に apikey を必須化しました。
本モジュールは環境変数 STOOQ_API_KEY を読み込み、認証付きで日次データを取得します。
"""
import logging
import os
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

STOOQ_BASE_URL = "https://stooq.com/q/d/l/"


def _get_api_key() -> Optional[str]:
    return os.environ.get("STOOQ_API_KEY") or None


def fetch_stooq_daily(ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """Stooq から日次データを取得

    Args:
        ticker: Stooqティッカー (例: ``^tpx``)
        start: 開始日 ``YYYYMMDD`` または ``YYYY-MM-DD``
        end:   終了日 同上

    Returns:
        ``Date, Open, High, Low, Close, Volume`` を持つ DataFrame。失敗時 None。
    """
    api_key = _get_api_key()
    if not api_key:
        logger.error("[Stooq] STOOQ_API_KEY not set")
        return None

    d1 = start.replace("-", "")
    d2 = end.replace("-", "")
    url = f"{STOOQ_BASE_URL}?s={ticker}&d1={d1}&d2={d2}&i=d&apikey={api_key}"

    try:
        df = pd.read_csv(url)
    except Exception as e:
        logger.error(f"[Stooq] fetch failed for {ticker}: {e}")
        return None

    if df.empty or "Date" not in df.columns or "Close" not in df.columns:
        logger.error(f"[Stooq] unexpected response for {ticker}: cols={list(df.columns)}")
        return None

    df["Date"] = pd.to_datetime(df["Date"])
    return df
