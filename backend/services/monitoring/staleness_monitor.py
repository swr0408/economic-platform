# -*- coding: utf-8 -*-
"""
キャッシュ鮮度モニタ (取りこぼし検知ガード)

全 backend/data/cache/**/*.json を走査し、各キャッシュの「最新データ日付」と
「last_updated」を抽出。系列の頻度を日付間隔から推定し、期待リリース間隔より
大幅に遅れているものを STUCK / WRITER_STOPPED / LAGGING に分類して返す。

さらに、系列日付を持たない成果物も mtime ベースで監視する (従来の盲点対策):
  - data/cache + data/picture 配下の PNG/CSV/XLSX (スクリーンショット・DL成果物)
  - data/manual_update 配下 (手動更新の放置検知、ディレクトリ単位)
  - data/cache/earnings (カレンダーは将来日付のみで系列判定不能 → mtime で判定)
mtime 閾値超過は STUCK として返す (`check: "mtime"` フィールドで区別可能)。
系列判定も mtime 判定もできない JSON は UNMONITORED として列挙し、盲点を
API から enumerable にする。

目的:
  ソース機構の劣化 (URL/資産ID変更、403/502、フォーマット変更等) で
  「再取得は走るのにデータが進まない」silent failure を**可視化**すること。
  個別サービスを書き換えずに 754+ キャッシュ全体を一括監視できる。

外部 API は叩かない (読み取り専用)。FMP カレンダー DB が利用可能なら、
country 指標について「実際に公表済みの最新 actual 日付」と突き合わせて精度を上げる。
"""
from __future__ import annotations

import asyncio
import glob
import json
import multiprocessing
import os
import re
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional

from pathlib import Path

import logging

logger = logging.getLogger(__name__)

# backend/data 配下の監視対象ルート
DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
CACHE_ROOT = DATA_ROOT / "cache"
PICTURE_ROOT = DATA_ROOT / "picture"
MANUAL_ROOT = DATA_ROOT / "manual_update"
JST = timezone(timedelta(hours=9))

_DATE_KEYS = ["date", "period", "month", "quarter", "time", "datetime",
              "timestamp", "ref_date", "obs_date"]
_LU_KEYS = ["last_updated", "lastUpdated", "updated_at", "last_update",
            "fetched_at", "cached_at"]
_SERIES_KEYS = ["data", "series", "observations", "values", "history",
                "points", "items"]

# 参照のないオーファンキャッシュ (検知対象外)
_IGNORE_SUBSTR = (
    "advance_decline_daily_ad",
    "advance_decline_prime_codes",
    "/test_",
    "test_response",
    "test_unemp",
    "test_estat",
    "_test",            # *_test.png / *_test.xlsx 等のテスト成果物
    "/temp/",           # 一時作業ディレクトリ
    "_temp.",           # *_temp.xlsx 等の一時ファイル
    "wgc_etf_template", # 静的テンプレート (更新されないのが正常)
)

# ---------------------------------------------------------------------------
# mtime ベース監視ルール (PNG / CSV / XLSX / manual_update / earnings)
#
# 系列日付を持たない成果物 (スクリーンショット PNG、ダウンロード CSV/XLSX、
# 手動更新ファイル、将来日付しか含まない earnings カレンダー) は系列ベースの
# 鮮度判定ができず従来は完全な盲点だった。これらは「ファイル mtime の経過日数
# > 閾値」で凍結を検知する (mtime = 最後に書き込みが成功した時刻なので、
# 書き込みが止まった silent failure を直接捕捉できる)。閾値超過は STUCK。
# ---------------------------------------------------------------------------

# 拡張子ごとのデフォルト閾値 (日)。下の _MTIME_OVERRIDES が優先。
_MTIME_DEFAULT_THRESHOLDS = {
    ".png": 7.0,    # 日次スクリーンショット成果物 (週末・祝日を考慮して 7 日)
    ".jpg": 7.0,
    ".jpeg": 7.0,
    ".csv": 90.0,   # ほぼ slow-moving なダウンロード成果物
    ".xlsx": 90.0,
    ".xls": 90.0,
}

# パス別オーバーライド: (パス部分一致, 閾値日数, per_dir)
# 上から順に評価し最初に一致したルールを採用。
# per_dir=True は「日付付きアーカイブのディレクトリ」(古いファイルが残るのが
# 正常) を意味し、ディレクトリ内で最も新しいファイルの mtime だけを評価する。
_MTIME_OVERRIDES = (
    ("usa/fomc_projections/", 120.0, True),        # FOMC SEP (四半期)
    ("usa/fomc_table1/", 120.0, True),             # FOMC Table1 (四半期)
    ("japan/monetary_policy/outlook_images/", 120.0, True),   # 日銀展望レポート (1/4/7/10月)
    ("switzerland/monetary_policy/inflation_forecast_images/", 120.0, True),  # SNB (四半期)
    ("uk/housing/rics_survey_images/", 60.0, True),  # RICS 月次サーベイ画像
    ("market/vx_contracts/", 14.0, True),          # VIX 限月別アーカイブ: 最新限月のみ評価
    ("australia/inflation/nab_chart", 45.0, False),  # NAB 月次サーベイのチャート
    ("newzealand/inflation/anz_business_outlook", 45.0, False),  # ANZ 月次
    ("china/economy/cn_li_keqiang_index", 45.0, False),  # 月次合成
)

# manual_update のデフォルト閾値 (手動更新の放置を緩めに検知)
_MANUAL_DEFAULT_THRESHOLD = 45.0
# manual_update 配下のオーバーライド: (MANUAL_ROOT 相対パスの部分一致, 閾値日数)
_MANUAL_OVERRIDES = (
    ("seasonality/", 400.0),            # 季節性データは年 1 回の再生成で十分
    ("yearly/", 400.0),                 # 年次更新フォルダ
    ("monthly/switzerland_snb/", 400.0),  # SNB 年間カレンダー (.ics, 年次)
)

# earnings (JSON だがカレンダーは将来日付のみ → 系列判定不能なので mtime で判定)
_EARNINGS_CALENDAR_THRESHOLD = 8.0     # カレンダーは日次〜週次で再取得されるはず
_EARNINGS_FINANCIALS_THRESHOLD = 120.0  # 決算は四半期

# ---------------------------------------------------------------------------
# 系列ベース判定の「期待リリース間隔」オーバーライド: (パス部分一致, 間隔日数)
#
# データ自体は日次 (営業日) でも、上流が週次でまとめて公表するソースは、
# 日付間隔から推定した interval=1日 → 閾値 max(8, 2.5×1)=8日 となり、
# 最新データ齢が 4〜10 日で振動するため毎週末に誤検知する (2026-06-13 に確認)。
# 実際の公表サイクルを明示して閾値を引き上げる。
# interval=7 ⇒ 閾値 max(8, 2.5×7)=17.5日 — 本物の凍結 (2サイクル超) は引き続き捕捉。
# ---------------------------------------------------------------------------
_INTERVAL_OVERRIDES = (
    ("market/gold_premium_cache.json", 7.0),          # WGC GoldHub: 毎週火曜に前週金曜分まで公表
    ("usa/employment/jolts_indeed_cache.json", 7.0),  # FRED IHLIDXUS: Indeed Hiring Lab が週次反映
)


def _parse_date(s: Any) -> Optional[datetime]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        try:
            v = float(s)
            if v > 1e11:
                v /= 1000.0
            if 1e8 < v < 2e10:
                return datetime.fromtimestamp(v, tz=timezone.utc)
        except Exception:
            return None
        return None
    if not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    m = re.match(r"^(\d{4})[-\s]?Q([1-4])$", s, re.I)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        return datetime(y, (q - 1) * 3 + 1, 1)
    for f in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m", "%Y%m%d"):
        try:
            return datetime.strptime(s, f)
        except Exception:
            continue
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            pass
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1)
        except Exception:
            pass
    return None


def _to_naive_jst(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo:
        return dt.astimezone(JST).replace(tzinfo=None)
    return dt


def _extract_dates_from_list(lst: list) -> List[datetime]:
    out: List[datetime] = []
    for item in lst:
        if isinstance(item, dict):
            for k in _DATE_KEYS:
                if k in item:
                    d = _parse_date(item[k])
                    if d:
                        out.append(d)
                        break
        elif isinstance(item, str):
            d = _parse_date(item)
            if d:
                out.append(d)
    return out


def _find_series_dates(obj: Any, depth: int = 0) -> List[datetime]:
    if depth > 4:
        return []
    best: List[datetime] = []
    if isinstance(obj, list):
        ds = _extract_dates_from_list(obj)
        if len(ds) > len(best):
            best = ds
    elif isinstance(obj, dict):
        key_ds = [d for d in (_parse_date(k) for k in obj.keys()) if d]
        if len(key_ds) >= 3:
            best = key_ds
        for k in _SERIES_KEYS:
            if k in obj:
                ds = _find_series_dates(obj[k], depth + 1)
                if len(ds) > len(best):
                    best = ds
        for v in obj.values():
            if isinstance(v, (list, dict)):
                ds = _find_series_dates(v, depth + 1)
                if len(ds) > len(best):
                    best = ds
    return best


def _get_last_updated(obj: Any) -> Optional[datetime]:
    if not isinstance(obj, dict):
        return None
    for k in _LU_KEYS:
        if k in obj:
            d = _parse_date(obj[k])
            if d:
                return d
    return None


def _infer_interval_days(dates: List[datetime]) -> Optional[float]:
    if len(dates) < 3:
        return None
    ds = sorted(set(dates))[-15:]
    deltas = [(ds[i + 1] - ds[i]).days for i in range(len(ds) - 1)
              if (ds[i + 1] - ds[i]).days > 0]
    return median(deltas) if deltas else None


def _classify_freq(interval: Optional[float]) -> str:
    if interval is None:
        return "unknown"
    if interval <= 3.5:
        return "daily"
    if interval <= 10:
        return "weekly"
    if interval <= 20:
        return "biweekly"
    if interval <= 45:
        return "monthly"
    if interval <= 135:
        return "quarterly"
    if interval <= 250:
        return "semiannual"
    return "annual"


def _categorize(days_since_latest: Optional[int], days_since_update: Optional[int],
                interval: Optional[float]) -> Optional[str]:
    """フラグ対象と分類を判定。フラグ不要なら None。"""
    if days_since_latest is None or interval is None:
        return None
    # データが「2.5 サイクル超 かつ 8 日超」遅れていなければ正常ラグとみなす。
    # 月次 (interval~31) は 2.5*31≒78日。月次指標が公表後 4-6 週遅れて反映される
    # 通常ラグ (例: 6/11 時点で 4 月が最新) を誤検知しないための係数。
    # 数ヶ月単位の本物の凍結 (例: 12 月で停止 = 190 日超) は確実に捕捉する。
    if not (days_since_latest >= max(8, 2.5 * interval)):
        return None
    if days_since_update is not None and days_since_update <= 3:
        # 再取得は最近走っているのにデータが進んでいない = silent failure
        return "STUCK"
    if days_since_update is None or days_since_update >= max(8, 2.0 * interval):
        return "WRITER_STOPPED"
    return "LAGGING"


def _scan_mtime_artifacts() -> List[Dict[str, Any]]:
    """系列日付を持たない成果物の mtime ベース凍結検知

    対象: PNG/JPG/CSV/XLSX (cache + picture), manual_update 配下,
          earnings JSON (将来日付のみで系列判定不能)。
    閾値超過のみ STUCK (`check: "mtime"`) として返す。
    """
    import time as _time

    now_ts = _time.time()
    candidates: List[tuple] = []  # (mtime, label, threshold, group_key or None)

    def _collect(path: Path, label: str, threshold: float, group: Optional[str]):
        try:
            mt = path.stat().st_mtime
        except OSError:
            return
        candidates.append((mt, label, threshold, group))

    # 1) cache + picture 配下の PNG/CSV/XLSX
    for root, prefix in ((CACHE_ROOT, ""), (PICTURE_ROOT, "picture/")):
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(root)).replace("\\", "/")
            if any(s in ("/" + rel) or s in rel for s in _IGNORE_SUBSTR):
                continue
            ext = p.suffix.lower()
            label = prefix + rel

            # earnings JSON は mtime で判定 (系列は将来日付のみ)
            if prefix == "" and rel.startswith("earnings/") and ext == ".json":
                thr = (_EARNINGS_CALENDAR_THRESHOLD if "calendar" in p.name
                       else _EARNINGS_FINANCIALS_THRESHOLD)
                _collect(p, label, thr, None)
                continue

            if ext not in _MTIME_DEFAULT_THRESHOLDS:
                continue
            thr = _MTIME_DEFAULT_THRESHOLDS[ext]
            group = None
            for sub, o_thr, per_dir in _MTIME_OVERRIDES:
                if sub in rel:
                    thr = o_thr
                    if per_dir:
                        group = sub  # ディレクトリ内最新ファイルのみ評価
                    break
            _collect(p, label, thr, group)

    # 2) manual_update 配下 (トップレベルディレクトリ単位で最新ファイルのみ評価)
    if MANUAL_ROOT.exists():
        for p in MANUAL_ROOT.rglob("*"):
            if not p.is_file():
                continue
            # ドキュメント類 (更新手順書等) はデータではないため対象外
            if p.suffix.lower() in (".md", ".txt"):
                continue
            rel = str(p.relative_to(MANUAL_ROOT)).replace("\\", "/")
            if any(s in rel for s in _IGNORE_SUBSTR):
                continue
            thr = _MANUAL_DEFAULT_THRESHOLD
            for sub, o_thr in _MANUAL_OVERRIDES:
                if sub in rel:
                    thr = o_thr
                    break
            top = rel.split("/")[0] if "/" in rel else rel
            _collect(p, f"manual_update/{rel}", thr, f"manual:{top}:{thr}")

    # per_dir/グループ集約: グループ内で最も新しいファイルだけを代表として評価
    singles: List[tuple] = []
    by_group: Dict[str, tuple] = {}
    for item in candidates:
        mt, label, thr, group = item
        if group is None:
            singles.append(item)
        else:
            cur = by_group.get(group)
            if cur is None or mt > cur[0]:
                by_group[group] = item

    rows: List[Dict[str, Any]] = []
    for mt, label, thr, _group in singles + list(by_group.values()):
        age_days = (now_ts - mt) / 86400.0
        if age_days <= thr:
            continue
        rows.append({
            "file": label,
            "category": "STUCK",
            "check": "mtime",
            "freq": None,
            "interval_days": None,
            "latest": None,
            "days_since_latest": round(age_days, 1),
            "last_updated": datetime.fromtimestamp(mt).strftime("%Y-%m-%d"),
            "days_since_update": round(age_days, 1),
            "overdue_ratio": round(age_days / thr, 2) if thr else None,
            "threshold_days": thr,
        })
    return rows


# ファイル解析結果(系列日付 + last_updated)の mtime ベースキャッシュ。
# scan_stale_caches は全 760+ キャッシュを json.load + 深い再帰走査するため 1回 ~12秒の
# CPU(GIL占有)処理になり、イベントループを飢えさせて全APIが遅延する事象があった(2026-06-14)。
# 解析結果はファイル内容(=mtime)にのみ依存するため、mtime 不変なら再解析せず再利用し、
# 2回目以降のスキャンを大幅に高速化する(変更ファイルのみ再解析)。
_FILE_PARSE_CACHE: Dict[str, Any] = {}  # path -> (mtime, all_dates, last_updated)


def scan_stale_caches(now: Optional[datetime] = None,
                      include_ok: bool = False) -> Dict[str, Any]:
    """全キャッシュを走査して鮮度を判定する。

    Returns: {
      "generated_at": iso,
      "total": int, "flagged": int,
      "counts": {"STUCK":.., "WRITER_STOPPED":.., "LAGGING":..},
      "items": [ {file, category, freq, interval, latest, days_since_latest,
                  last_updated, days_since_update, overdue_ratio}, ... ]  # severity降順
    }
    """
    now_dt = _to_naive_jst(now or datetime.now(JST))
    rows: List[Dict[str, Any]] = []
    files = glob.glob(str(CACHE_ROOT / "**" / "*.json"), recursive=True)
    for f in files:
        rel = os.path.relpath(f, CACHE_ROOT).replace("\\", "/")
        if any(s in ("/" + rel) or s in rel for s in _IGNORE_SUBSTR):
            continue
        # earnings JSON はカレンダーが将来日付のみで系列判定が永久に None になる
        # → mtime ベース (_scan_mtime_artifacts) で監視するためここでは除外
        if rel.startswith("earnings/"):
            continue
        # mtime 不変なら前回の解析結果(系列日付 + last_updated)を再利用し、
        # json.load + 深い再帰走査(高コスト)をスキップする。
        try:
            mtime = os.path.getmtime(f)
        except OSError:
            mtime = None
        cached = _FILE_PARSE_CACHE.get(f)
        if cached is not None and mtime is not None and cached[0] == mtime:
            all_dates, last_updated = cached[1], cached[2]
        else:
            try:
                with open(f, encoding="utf-8") as _fh:
                    obj = json.load(_fh)
            except Exception as e:
                rows.append({"file": rel, "category": "PARSE_ERROR", "error": str(e)})
                continue
            all_dates = [_to_naive_jst(d) for d in _find_series_dates(obj) if d]
            last_updated = _to_naive_jst(_get_last_updated(obj))
            if mtime is not None:
                _FILE_PARSE_CACHE[f] = (mtime, all_dates, last_updated)
        # 将来日付 (予測値/プロジェクション) は「実績の鮮度」評価から除外する。
        # 例: CBO NAIRU(NROU) は 2036 年までの予測を含み、除外しないと latest が未来になり
        # FRED/CBO が更新を止めても永遠に stale 判定されない。実績の最新 (<=今日) で評価する。
        dates = [d for d in all_dates if d <= now_dt]
        latest = max(dates) if dates else None
        interval = _infer_interval_days(dates)
        for sub, o_int in _INTERVAL_OVERRIDES:
            if sub in rel:
                interval = o_int
                break
        dsl = (now_dt - latest).days if latest else None
        dsu = (now_dt - last_updated).days if last_updated else None
        cat = _categorize(dsl, dsu, interval)
        if cat is None:
            # 系列日付が3点未満等で鮮度判定不能なファイルは盲点として列挙可能にする
            if latest is None and include_ok:
                cat = "UNMONITORED"
            elif not include_ok:
                continue
        overdue = round(dsl / interval, 2) if (dsl is not None and interval) else None
        rows.append({
            "file": rel,
            "category": cat or "OK",
            "freq": _classify_freq(interval),
            "interval_days": round(interval, 1) if interval else None,
            "latest": latest.strftime("%Y-%m-%d") if latest else None,
            "days_since_latest": dsl,
            "last_updated": last_updated.strftime("%Y-%m-%d") if last_updated else None,
            "days_since_update": dsu,
            "overdue_ratio": overdue,
            "n_points": len(dates),
        })

    # mtime ベースの成果物監視 (PNG/CSV/XLSX/manual_update/earnings) を統合
    try:
        rows.extend(_scan_mtime_artifacts())
    except Exception as e:
        logger.error(f"[StalenessMonitor] mtime artifact scan failed: {e}")

    order = {"STUCK": 0, "WRITER_STOPPED": 1, "LAGGING": 2, "PARSE_ERROR": 3,
             "UNMONITORED": 4, "OK": 9}
    flagged = [r for r in rows if r["category"] not in ("OK",)]
    flagged.sort(key=lambda r: (order.get(r["category"], 8),
                                -(r.get("overdue_ratio") or 0)))
    counts: Dict[str, int] = {}
    for r in flagged:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    items = flagged
    if include_ok:
        items = flagged + [r for r in rows if r["category"] == "OK"]
    return {
        "generated_at": (now or datetime.now(JST)).isoformat(),
        "total": len(files),
        "flagged": len(flagged),
        "counts": counts,
        "items": items,
    }


# ---- 別プロセス実行ラッパー（イベントループを塞がない）----
# scan_stale_caches は 760+ キャッシュを走査する ~12秒の CPU/IO 処理。to_thread だと
# json 解析等で GIL を握りメインのイベントループを飢えさせ、全API(ログイン含む)が遅延する
# 事象があった(2026-06-14)。専用の子プロセス(spawn, 1ワーカー)で実行し、メインプロセスの
# GIL/ループを一切塞がないようにする。子プロセスは再利用されるため _FILE_PARSE_CACHE も温まる。
_scan_pool: Optional[ProcessPoolExecutor] = None


def _get_scan_pool() -> ProcessPoolExecutor:
    global _scan_pool
    if _scan_pool is None:
        # spawn: マルチスレッドな uvicorn ワーカーから fork する危険(ロック継承)を避ける
        _scan_pool = ProcessPoolExecutor(
            max_workers=1, mp_context=multiprocessing.get_context("spawn")
        )
    return _scan_pool


async def scan_stale_caches_async(include_ok: bool = False) -> Dict[str, Any]:
    """scan_stale_caches を別プロセスで実行する非同期版。

    重い走査をメインのイベントループ(GIL)から切り離し、スキャン中もAPIが応答できるようにする。
    子プロセスの起動/通信に失敗した場合はループを塞がないよう to_thread にフォールバックする。
    """
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_get_scan_pool(), scan_stale_caches, None, include_ok)
    except Exception as e:
        logger.warning(f"[StalenessMonitor] process-pool scan failed ({e}); falling back to thread")
        return await asyncio.to_thread(scan_stale_caches, None, include_ok)


def log_stale_summary(result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """スケジューラから呼ぶ用: 結果をログに WARNING で出す。

    result を渡すと再スキャンせずそれを使う（別プロセスで取得済みの結果をログ化する用途）。
    """
    if result is None:
        result = scan_stale_caches()
    stuck = [r for r in result["items"] if r["category"] == "STUCK"]
    logger.warning(
        "[StalenessMonitor] flagged=%d %s (total=%d). "
        "STUCK (writer runs but data frozen, requires investigation):",
        result["flagged"], result["counts"], result["total"],
    )
    for r in stuck[:60]:
        logger.warning(
            "[StalenessMonitor] STUCK %s latest=%s (%sd late, %s) upd=%s",
            r["file"], r["latest"], r["days_since_latest"], r["freq"],
            r["last_updated"],
        )
    return result
