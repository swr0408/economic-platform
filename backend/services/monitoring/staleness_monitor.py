# -*- coding: utf-8 -*-
"""
キャッシュ鮮度モニタ (取りこぼし検知ガード)

全 backend/data/cache/**/*.json を走査し、各キャッシュの「最新データ日付」と
「last_updated」を抽出。系列の頻度を日付間隔から推定し、期待リリース間隔より
大幅に遅れているものを STUCK / WRITER_STOPPED / LAGGING に分類して返す。

目的:
  ソース機構の劣化 (URL/資産ID変更、403/502、フォーマット変更等) で
  「再取得は走るのにデータが進まない」silent failure を**可視化**すること。
  個別サービスを書き換えずに 754 キャッシュ全体を一括監視できる。

外部 API は叩かない (読み取り専用)。FMP カレンダー DB が利用可能なら、
country 指標について「実際に公表済みの最新 actual 日付」と突き合わせて精度を上げる。
"""
from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional

from pathlib import Path

import logging

logger = logging.getLogger(__name__)

# backend/data/cache
CACHE_ROOT = Path(__file__).resolve().parents[2] / "data" / "cache"
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
        try:
            obj = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            rows.append({"file": rel, "category": "PARSE_ERROR", "error": str(e)})
            continue
        all_dates = [_to_naive_jst(d) for d in _find_series_dates(obj) if d]
        # 将来日付 (予測値/プロジェクション) は「実績の鮮度」評価から除外する。
        # 例: CBO NAIRU(NROU) は 2036 年までの予測を含み、除外しないと latest が未来になり
        # FRED/CBO が更新を止めても永遠に stale 判定されない。実績の最新 (<=今日) で評価する。
        dates = [d for d in all_dates if d <= now_dt]
        last_updated = _to_naive_jst(_get_last_updated(obj))
        latest = max(dates) if dates else None
        interval = _infer_interval_days(dates)
        dsl = (now_dt - latest).days if latest else None
        dsu = (now_dt - last_updated).days if last_updated else None
        cat = _categorize(dsl, dsu, interval)
        if cat is None and not include_ok:
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

    order = {"STUCK": 0, "WRITER_STOPPED": 1, "LAGGING": 2, "PARSE_ERROR": 3, "OK": 9}
    flagged = [r for r in rows if r["category"] not in ("OK",)]
    flagged.sort(key=lambda r: (order.get(r["category"], 8),
                                -(r.get("overdue_ratio") or 0)))
    counts: Dict[str, int] = {}
    for r in flagged:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    return {
        "generated_at": (now or datetime.now(JST)).isoformat(),
        "total": len(files),
        "flagged": len(flagged),
        "counts": counts,
        "items": flagged,
    }


def log_stale_summary() -> Dict[str, Any]:
    """スケジューラから呼ぶ用: 結果をログに WARNING で出す。"""
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
