"""
シーズナリティ分析サービス。

各銘柄の monthly_stats / intramonth_path / daily_stats JSON を読み込み、
推奨閾値に基づき「傾向の強い銘柄×月」を抽出してリスト化する。

判定指標と閾値（デフォルト）:
  mean      : |mean| >= 1.0% かつ p_value < 0.05
  median    : |median| >= 1.0%
  neg_rate  : <= 0.20（高勝率）または >= 0.80（高負け率）
  table     : mean / median / neg_rate が同方向で全て閾値を満たす（最強）
  intramonth: 月末累積平均 |cum| >= 1.0%
  daily     : 1営業日で |mean_pct| >= 0.5%（サンプル n >= 10）

期間:
  full   ... 2004-2025（CSV由来）
  recent ... 直近10年 (2016-2025)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    from backend.config import SEASONALITY_STATS_DIR
except ImportError:
    from config import SEASONALITY_STATS_DIR


# 閾値（推奨デフォルト）
TH_MEAN_ABS = 1.0           # %
TH_MEAN_P = 0.05
TH_MEDIAN_ABS = 1.0          # %
TH_NEG_RATE_LOW = 0.20
TH_NEG_RATE_HIGH = 0.80
TH_INTRAMONTH_ABS = 1.0      # %
TH_DAILY_ABS = 0.5           # %
TH_DAILY_MIN_N = 10

# キャッシュ（元データは手動更新のみのため24時間TTL）
_cache: Optional[Dict] = None
_cache_ts: float = 0.0
_CACHE_TTL: float = 86400.0  # 24時間


def _safe(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _load_symbol_jsons(symbol: str) -> Optional[Dict]:
    """1銘柄分の3JSONを読み込む。読めなければ None。"""
    base = SEASONALITY_STATS_DIR / symbol
    monthly = base / "monthly_stats.json"
    intramonth = base / "intramonth_path.json"
    daily = base / "daily_stats.json"
    if not (monthly.exists() and intramonth.exists() and daily.exists()):
        return None
    try:
        with open(monthly, "r", encoding="utf-8") as f:
            m = json.load(f)
        with open(intramonth, "r", encoding="utf-8") as f:
            ip = json.load(f)
        with open(daily, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return None
    return {"monthly": m, "intramonth": ip, "daily": d}


def _eval_monthly(symbol: str, month_obj: Dict, period_key: str) -> List[Dict]:
    """monthly_stats の単月単期間からシグナルイベントを抽出。"""
    s = month_obj.get(period_key) or {}
    n = s.get("n") or 0
    if n < 5:  # 統計的信頼性が低すぎる月はスキップ
        return []

    events: List[Dict] = []
    mean = _safe(s.get("mean"))
    median = _safe(s.get("median"))
    neg_rate = _safe(s.get("neg_rate"))
    p_value = _safe(s.get("p_value"))
    std = _safe(s.get("std"))

    # mean
    if mean is not None and abs(mean) >= TH_MEAN_ABS and p_value is not None and p_value < TH_MEAN_P:
        events.append({
            "symbol": symbol,
            "month": month_obj["month"],
            "period": period_key,
            "chart": "mean",
            "direction": "bullish" if mean > 0 else "bearish",
            "metric": {"mean": mean, "p_value": p_value, "n": n},
        })

    # median
    if median is not None and abs(median) >= TH_MEDIAN_ABS:
        events.append({
            "symbol": symbol,
            "month": month_obj["month"],
            "period": period_key,
            "chart": "median",
            "direction": "bullish" if median > 0 else "bearish",
            "metric": {"median": median, "n": n},
        })

    # neg_rate
    if neg_rate is not None:
        if neg_rate <= TH_NEG_RATE_LOW:
            events.append({
                "symbol": symbol,
                "month": month_obj["month"],
                "period": period_key,
                "chart": "neg_rate",
                "direction": "bullish",
                "metric": {"neg_rate": neg_rate, "n": n},
            })
        elif neg_rate >= TH_NEG_RATE_HIGH:
            events.append({
                "symbol": symbol,
                "month": month_obj["month"],
                "period": period_key,
                "chart": "neg_rate",
                "direction": "bearish",
                "metric": {"neg_rate": neg_rate, "n": n},
            })

    # table（最強シグナル: mean / median / neg_rate が同方向で全条件 OK）
    if mean is not None and median is not None and neg_rate is not None and p_value is not None:
        bull = (
            mean >= TH_MEAN_ABS
            and median >= TH_MEDIAN_ABS
            and neg_rate <= TH_NEG_RATE_LOW
            and p_value < TH_MEAN_P
        )
        bear = (
            mean <= -TH_MEAN_ABS
            and median <= -TH_MEDIAN_ABS
            and neg_rate >= TH_NEG_RATE_HIGH
            and p_value < TH_MEAN_P
        )
        if bull or bear:
            events.append({
                "symbol": symbol,
                "month": month_obj["month"],
                "period": period_key,
                "chart": "table",
                "direction": "bullish" if bull else "bearish",
                "metric": {
                    "mean": mean,
                    "median": median,
                    "neg_rate": neg_rate,
                    "p_value": p_value,
                    "std": std,
                    "n": n,
                },
            })

    return events


def _eval_intramonth(symbol: str, month_obj: Dict, period_key: str) -> List[Dict]:
    """intramonth_path の単月単期間（月末累積平均）からシグナル抽出。"""
    s = month_obj.get(period_key) or {}
    cum = s.get("cum_mean_pct") or []
    days = s.get("trading_days") or []
    if not cum:
        return []
    last_cum = _safe(cum[-1])
    if last_cum is None:
        return []
    if abs(last_cum) < TH_INTRAMONTH_ABS:
        return []

    return [{
        "symbol": symbol,
        "month": month_obj["month"],
        "period": period_key,
        "chart": "intramonth",
        "direction": "bullish" if last_cum > 0 else "bearish",
        "metric": {
            "cum_end": last_cum,
            "days": days[-1] if days else None,
        },
    }]


def _eval_daily(symbol: str, month_obj: Dict, period_key: str) -> List[Dict]:
    """daily_stats の単月単期間から、スパイク日（|mean_pct|>=0.5%）を抽出。"""
    cells = month_obj.get(period_key) or []
    events: List[Dict] = []
    for cell in cells:
        n = cell.get("n") or 0
        if n < TH_DAILY_MIN_N:
            continue
        mp = _safe(cell.get("mean_pct"))
        if mp is None:
            continue
        if abs(mp) >= TH_DAILY_ABS:
            events.append({
                "symbol": symbol,
                "month": month_obj["month"],
                "period": period_key,
                "chart": "daily",
                "direction": "bullish" if mp > 0 else "bearish",
                "metric": {
                    "day": cell.get("day"),
                    "mean_pct": mp,
                    "neg_rate": _safe(cell.get("neg_rate")),
                    "n": n,
                },
            })
    return events


def _build_events(symbol: str, payload: Dict) -> List[Dict]:
    """1銘柄分の全イベントを構築。"""
    out: List[Dict] = []
    for m in payload["monthly"].get("months", []):
        out.extend(_eval_monthly(symbol, m, "full"))
        out.extend(_eval_monthly(symbol, m, "recent"))
    for m in payload["intramonth"].get("months", []):
        out.extend(_eval_intramonth(symbol, m, "full"))
        out.extend(_eval_intramonth(symbol, m, "recent"))
    for m in payload["daily"].get("months", []):
        out.extend(_eval_daily(symbol, m, "full"))
        out.extend(_eval_daily(symbol, m, "recent"))
    return out


def _detect_dual_period_agreement(events: List[Dict]) -> List[Dict]:
    """同銘柄×同月×同チャートで、fullとrecentの両期間で同方向のシグナルを検出。

    最強シグナル「両期間一致」を別タグとして追加返却。
    """
    by_key: Dict[tuple, Dict[str, Dict]] = {}
    for e in events:
        k = (e["symbol"], e["month"], e["chart"])
        by_key.setdefault(k, {})[e["period"]] = e

    duals: List[Dict] = []
    for k, periods in by_key.items():
        full = periods.get("full")
        recent = periods.get("recent")
        if not (full and recent):
            continue
        if full["direction"] != recent["direction"]:
            continue
        duals.append({
            "symbol": k[0],
            "month": k[1],
            "period": "both",
            "chart": k[2],
            "direction": full["direction"],
            "metric": {
                "full": full["metric"],
                "recent": recent["metric"],
            },
        })
    return duals


def _periods_label(monthly_json: Dict) -> Dict[str, str]:
    p = monthly_json.get("periods", {})
    return {
        "full": p.get("full", {}).get("label", "full"),
        "recent": p.get("recent", {}).get("label", "recent"),
    }


def build_analysis() -> Dict:
    """全銘柄の分析を構築（in-memory キャッシュあり）。"""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _CACHE_TTL:
        return _cache

    base = SEASONALITY_STATS_DIR
    if not base.exists():
        return {"events": [], "symbols": [], "periods": {}, "thresholds": _thresholds_dict()}

    all_events: List[Dict] = []
    symbols: List[str] = []
    periods_label: Dict[str, str] = {}

    for sym_dir in sorted(base.iterdir()):
        if not sym_dir.is_dir():
            continue
        symbol = sym_dir.name
        payload = _load_symbol_jsons(symbol)
        if payload is None:
            continue
        symbols.append(symbol)
        if not periods_label:
            periods_label = _periods_label(payload["monthly"])

        events = _build_events(symbol, payload)
        # 両期間一致シグナルも追加
        events += _detect_dual_period_agreement(events)
        all_events.extend(events)

    result = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "periods": periods_label,
        "thresholds": _thresholds_dict(),
        "symbols": symbols,
        "events": all_events,
    }
    _cache = result
    _cache_ts = now
    return result


def _thresholds_dict() -> Dict:
    return {
        "mean_abs_pct": TH_MEAN_ABS,
        "mean_p_value": TH_MEAN_P,
        "median_abs_pct": TH_MEDIAN_ABS,
        "neg_rate_low": TH_NEG_RATE_LOW,
        "neg_rate_high": TH_NEG_RATE_HIGH,
        "intramonth_abs_pct": TH_INTRAMONTH_ABS,
        "daily_abs_pct": TH_DAILY_ABS,
        "daily_min_n": TH_DAILY_MIN_N,
    }


def invalidate_cache() -> None:
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0
