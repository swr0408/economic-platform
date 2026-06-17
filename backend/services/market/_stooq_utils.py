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

# PoW ソルバーの時間バジェット (秒)。
# 期待試行回数は約 16^d。Stooq がアンチボット難易度 d を引き上げると総当たりが
# 事実上終わらず、1スレッドが 100% CPU を占有して GIL を握り、全 API (ログイン含む) が
# タイムアウトする事象があった。バジェット超過で打ち切り、last-good キャッシュへフォールバックする。
_POW_MAX_SECONDS = 8.0
_PAGE_SLEEP_SEC = 0.4
# 差分取得時に重ねて取り直す日数 (休日・改定ぶれ吸収)
_OVERLAP_DAYS = 7

# 単一レスポンス本文の読み込み上限。
# requests の timeout は「接続/バイト間」タイムアウトに過ぎず、本文の合計読み込み
# 時間や展開後サイズを制限しない。Stooq が切れ目なく (または巨大な gzip で)
# チャンクを流し続けると resp.text の解凍 (urllib3 read_chunked→zlib decompress) が
# 事実上無限に CPU を焼き、1スレッドが GIL を握って全 API (inbox 含む) を飢えさせる
# 事象があった。合計時間と展開後バイト数で打ち切り、超過時は None→last-good フォールバック。
_MAX_READ_SECONDS = 20.0
_MAX_BODY_BYTES = 8 * 1024 * 1024  # 8MB (日次テーブル HTML は数十KB〜数百KB)

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


def _solve_pow(c: str, d: int, max_seconds: float = _POW_MAX_SECONDS) -> Optional[int]:
    """sha256(c+n) の16進表現が '0'*d で始まる最小の n を求める。

    期待試行回数は約 16^d。難易度が高いと総当たりが終わらず 1スレッドが CPU を
    焼き続けてイベントループを飢えさせるため、時間バジェットで打ち切る。
    打ち切った場合は None を返し、呼び出し側は last-good キャッシュへフォールバックする。
    """
    target = "0" * d
    deadline = time.monotonic() + max_seconds
    n = 0
    while True:
        if hashlib.sha256((c + str(n)).encode()).hexdigest().startswith(target):
            return n
        n += 1
        # 約26万回ごとに時刻をチェック (ハッシュ計算に対し十分軽い)
        if (n & 0x3FFFF) == 0 and time.monotonic() > deadline:
            logger.error(
                f"[Stooq] PoW give up: d={d} を {max_seconds}s 以内に解けず "
                f"({n:,} hashes) — アンチボット難易度が高すぎるためキャッシュにフォールバック"
            )
            return None


def _read_body_bounded(resp) -> Optional[bytes]:
    """レスポンス本文を「壁時計デッドライン＋最大バイト数」付きで読み切る。

    ``iter_content`` は content-encoding (gzip) を解凍済みのチャンクを逐次返すため、
    チャンク境界ごとに経過時間と累積サイズを点検でき、無限/巨大ストリームに対して
    1スレッドが GIL を握り続けるのを防げる。超過時は ``None`` を返す。
    成功時は解凍後の生バイト列を返す (呼び出し側で ``resp._content`` に格納し、
    以後 ``resp.text`` / ``resp.status_code`` が従来どおり使えるようにする)。
    """
    deadline = time.monotonic() + _MAX_READ_SECONDS
    chunks = []
    total = 0
    try:
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total > _MAX_BODY_BYTES:
                logger.error(
                    f"[Stooq] response body exceeded {_MAX_BODY_BYTES // (1024 * 1024)}MB "
                    f"— abort {resp.url}"
                )
                return None
            if time.monotonic() > deadline:
                logger.error(
                    f"[Stooq] response body read exceeded {_MAX_READ_SECONDS}s "
                    f"({total:,} bytes) — abort {resp.url}"
                )
                return None
    except requests.RequestException as e:
        logger.error(f"[Stooq] body read failed: {e}")
        return None
    finally:
        resp.close()
    return b"".join(chunks)


def _get_with_challenge(url: str, timeout: int = 30) -> Optional[requests.Response]:
    """GET し、PoW チャレンジページが返ったら解いて再取得する。

    本文は ``stream=True`` + :func:`_read_body_bounded` で時間/サイズ上限付きに読む。
    requests の ``timeout`` は本文の合計読み込み時間を縛らないため、これがないと
    Stooq の巨大/無限ストリームで解凍が暴走し、GIL 占有で全 API が遅延する。
    """
    session = _get_session()
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=timeout, stream=True)
        except requests.RequestException as e:
            logger.error(f"[Stooq] request failed: {e}")
            return None

        body = _read_body_bounded(resp)
        if body is None:
            # 時間/サイズ超過 or 読み込み失敗 → last-good キャッシュへフォールバック
            return None
        # 読み込み済み本文を埋め込み、resp.text / resp.status_code を従来どおり使えるようにする
        resp._content = body
        resp._content_consumed = True

        match = _CHALLENGE_RE.search(resp.text)
        if not match:
            return resp

        c, d = match.group(1), int(match.group(2))
        logger.info(f"[Stooq] solving anti-bot challenge (d={d}, attempt={attempt + 1})")
        n = _solve_pow(c, d)
        if n is None:
            # 難易度が高すぎて時間内に解けない → 再試行しても同じなので諦める
            return None
        try:
            vr = session.post(
                f"{STOOQ_BASE}/__verify",
                data={"c": c, "n": str(n)},
                timeout=timeout,
                stream=True,
            )
            _read_body_bounded(vr)  # verify 応答も上限付きで読み捨て (暴走スポットを残さない)
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
