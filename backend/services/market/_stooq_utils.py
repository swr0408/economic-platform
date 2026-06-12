"""Stooq 日次データ共通ユーティリティ

歴史:
- 2026年頃: CSV ダウンロード API (`/q/d/l/`) に apikey が必須化。
- 2026-06: CSV API が全シンボルで "Access denied" を返すようになり実質閉鎖。
  さらにサイト全体に JavaScript proof-of-work アンチボット (`/__verify`) が導入された。

現方式:
1. PoW チャレンジ (sha256(c+n) が "0"*d で始まる n を求めて POST /__verify) を
   Python で解き、auth クッキー付きセッションを確立する。
2. 歴史データは HTML の日次テーブル (`/q/d/?s=...&d1=...&d2=...&l=<page>`,
   1ページ約40行・日付降順) をページネーションでパースする。
3. ティッカー別のローカル増分キャッシュ
   (`data/cache/market/stooq_daily_{ticker}.json`) を持ち、
   2回目以降はキャッシュ末尾以降の差分ページのみ取得する
   (日次更新は通常1ページで完結。15年分の全ページ再取得を避ける)。

旧 CSV API も先に1回だけ試す (将来復活した場合に自動で軽量パスへ戻る)。
"""
import hashlib
import io
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

STOOQ_BASE = "https://stooq.com"
STOOQ_CSV_URL = f"{STOOQ_BASE}/q/d/l/"
STOOQ_HTML_URL = f"{STOOQ_BASE}/q/d/"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_CHALLENGE_RE = re.compile(r'const c="([^"]+)",d=(\d+)')

# ローカル増分キャッシュ
_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ページネーション暴走ガード (40行/ページ × 150 ≈ 24年分)
_MAX_PAGES = 150
_PAGE_SLEEP_SEC = 0.4
# 差分取得時に重ねて取り直す日数 (休日・改定ぶれ吸収)
_OVERLAP_DAYS = 7

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def _get_api_key() -> Optional[str]:
    return os.environ.get("STOOQ_API_KEY") or None


def _get_session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": _UA,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })
            _session = s
        return _session


def _solve_pow(c: str, d: int) -> int:
    """sha256(c+n) の16進表現が '0'*d で始まる最小の n を求める"""
    target = "0" * d
    n = 0
    while True:
        if hashlib.sha256((c + str(n)).encode()).hexdigest().startswith(target):
            return n
        n += 1


def _get_with_challenge(url: str, timeout: int = 30) -> Optional[requests.Response]:
    """GET し、PoW チャレンジページが返ったら解いて再取得する"""
    session = _get_session()
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=timeout)
        except requests.RequestException as e:
            logger.error(f"[Stooq] request failed: {e}")
            return None

        match = _CHALLENGE_RE.search(resp.text)
        if not match:
            return resp

        c, d = match.group(1), int(match.group(2))
        logger.info(f"[Stooq] solving anti-bot challenge (d={d}, attempt={attempt + 1})")
        n = _solve_pow(c, d)
        try:
            session.post(
                f"{STOOQ_BASE}/__verify",
                data={"c": c, "n": str(n)},
                timeout=timeout,
            )
        except requests.RequestException as e:
            logger.error(f"[Stooq] /__verify failed: {e}")
            return None
    logger.error("[Stooq] challenge loop did not converge")
    return None


# ──────────────────────────────────────────────
# 旧 CSV API (復活時の軽量パス)
# ──────────────────────────────────────────────

def _try_csv(ticker: str, d1: str, d2: str) -> Optional[pd.DataFrame]:
    api_key = _get_api_key()
    url = f"{STOOQ_CSV_URL}?s={ticker}&d1={d1}&d2={d2}&i=d"
    if api_key:
        url += f"&apikey={api_key}"
    resp = _get_with_challenge(url)
    if resp is None or resp.status_code != 200:
        return None
    text = resp.text
    if not text or "Date" not in text.splitlines()[0]:
        return None
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception:
        return None
    if df.empty or "Date" not in df.columns or "Close" not in df.columns:
        return None
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"])
    return df if not df.empty else None


# ──────────────────────────────────────────────
# HTML 日次テーブルのパース
# ──────────────────────────────────────────────

def _parse_history_table(html: str) -> Optional[pd.DataFrame]:
    """`/q/d/` ページから日次 OHLCV テーブルを抽出"""
    try:
        tables = pd.read_html(io.StringIO(html))
    except Exception:
        return None
    for t in tables:
        cols = [str(c) for c in t.columns]
        if "Date" not in cols or "Close" not in cols:
            continue
        df = t.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna(subset=["Close"])
        if df.empty:
            continue
        for col in ("Open", "High", "Low", "Volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                df[col] = None
        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]
    return None


def _fetch_html_range(ticker: str, d1: str, d2: str,
                      stop_before: Optional[datetime] = None) -> Optional[pd.DataFrame]:
    """HTML ページネーションで [d1, d2] の日次データを取得 (日付降順ページ)

    stop_before が指定された場合、ページ内の最古日付がそれ以前に達した時点で
    打ち切る (増分取得用)。
    """
    frames = []
    for page in range(1, _MAX_PAGES + 1):
        url = f"{STOOQ_HTML_URL}?s={ticker}&d1={d1}&d2={d2}&l={page}"
        resp = _get_with_challenge(url)
        if resp is None or resp.status_code != 200:
            break
        df = _parse_history_table(resp.text)
        if df is None or df.empty:
            break
        frames.append(df)
        oldest = df["Date"].min()
        if stop_before is not None and oldest <= stop_before:
            break
        if oldest <= pd.to_datetime(d1, format="%Y%m%d"):
            break
        # 1ページ未満しか返らない = 最終ページ
        if len(df) < 20:
            break
        time.sleep(_PAGE_SLEEP_SEC)
    else:
        logger.warning(f"[Stooq] page cap ({_MAX_PAGES}) reached for {ticker}")

    if not frames:
        return None
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return out


# ──────────────────────────────────────────────
# ティッカー別ローカル増分キャッシュ
# ──────────────────────────────────────────────

def _cache_path(ticker: str) -> Path:
    safe = re.sub(r"[^a-z0-9_.-]", "_", ticker.lower())
    return _CACHE_DIR / f"stooq_daily_{safe}.json"


def _load_local(ticker: str) -> Dict[str, Dict]:
    path = _cache_path(ticker)
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[Stooq] local cache read failed for {ticker}: {e}")
    return {}


def _save_local(ticker: str, store: Dict[str, Dict]) -> None:
    try:
        _cache_path(ticker).write_text(
            json.dumps(store, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        logger.warning(f"[Stooq] local cache write failed for {ticker}: {e}")


def _df_to_store(df: pd.DataFrame) -> Dict[str, Dict]:
    store: Dict[str, Dict] = {}
    for _, row in df.iterrows():
        key = row["Date"].strftime("%Y-%m-%d")
        store[key] = {
            "Open": None if pd.isna(row.get("Open")) else float(row["Open"]),
            "High": None if pd.isna(row.get("High")) else float(row["High"]),
            "Low": None if pd.isna(row.get("Low")) else float(row["Low"]),
            "Close": float(row["Close"]),
            "Volume": None if pd.isna(row.get("Volume")) else float(row["Volume"]),
        }
    return store


def _store_to_df(store: Dict[str, Dict], start: datetime, end: datetime) -> Optional[pd.DataFrame]:
    rows = []
    for date_str, v in store.items():
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if start <= dt <= end:
            rows.append({"Date": dt, **v})
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def fetch_stooq_daily(ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """Stooq から日次データを取得 (CSV API → HTML スクレイプ + 増分キャッシュ)

    Args:
        ticker: Stooqティッカー (例: ``^tpx``)
        start: 開始日 ``YYYYMMDD`` または ``YYYY-MM-DD``
        end:   終了日 同上

    Returns:
        ``Date, Open, High, Low, Close, Volume`` を持つ DataFrame。失敗時 None。
    """
    d1 = start.replace("-", "")
    d2 = end.replace("-", "")
    start_dt = datetime.strptime(d1, "%Y%m%d")
    end_dt = datetime.strptime(d2, "%Y%m%d")

    # 1) 旧 CSV API (復活していれば最速)
    df = _try_csv(ticker, d1, d2)
    if df is not None:
        store = _load_local(ticker)
        store.update(_df_to_store(df))
        _save_local(ticker, store)
        return df

    # 2) HTML スクレイプ + 増分キャッシュ
    store = _load_local(ticker)
    if store:
        cache_max = max(store.keys())
        cache_max_dt = datetime.strptime(cache_max, "%Y-%m-%d")
        if cache_max_dt < end_dt:
            fetch_from = cache_max_dt - timedelta(days=_OVERLAP_DAYS)
            inc = _fetch_html_range(
                ticker,
                fetch_from.strftime("%Y%m%d"),
                d2,
                stop_before=pd.Timestamp(fetch_from),
            )
            if inc is not None and not inc.empty:
                store.update(_df_to_store(inc))
                _save_local(ticker, store)
            else:
                logger.warning(
                    f"[Stooq] incremental fetch returned nothing for {ticker} "
                    f"(cache last: {cache_max}); serving cached history"
                )
        # キャッシュが要求 start より新しい日付しか持たない場合は過去分を補完
        cache_min = min(store.keys())
        if datetime.strptime(cache_min, "%Y-%m-%d") > start_dt + timedelta(days=14):
            back = _fetch_html_range(
                ticker, d1, datetime.strptime(cache_min, "%Y-%m-%d").strftime("%Y%m%d")
            )
            if back is not None and not back.empty:
                store.update(_df_to_store(back))
                _save_local(ticker, store)
    else:
        full = _fetch_html_range(ticker, d1, d2)
        if full is None or full.empty:
            logger.error(f"[Stooq] fetch failed for {ticker} (CSV closed, HTML empty)")
            return None
        store = _df_to_store(full)
        _save_local(ticker, store)

    return _store_to_df(store, start_dt, end_dt)
