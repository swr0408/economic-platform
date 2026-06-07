"""
Seasonality Stats Builder

日足CSV(time, open, high, low, close)から月別統計と月内累積平均パスの
JSONを生成する。年に1回ほどの手動更新を想定。

入力:
  backend/data/manual_update/seasonality/input/{SYMBOL}/{SYMBOL}_1D.csv

出力:
  backend/data/manual_update/seasonality/output/{SYMBOL}/monthly_stats.json
  backend/data/manual_update/seasonality/output/{SYMBOL}/intramonth_path.json

使用方法:
  python build_stats.py --symbol SP500
  python build_stats.py --symbol SP500 --start-year 2004 --end-year 2025 --recent-years 10
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import median, stdev
from typing import Optional

import pandas as pd
from scipy import stats as scistats

# Paths
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent.parent  # backend/
SEASONALITY_BASE = BACKEND_DIR / "data" / "manual_update" / "seasonality"
INPUT_BASE = SEASONALITY_BASE / "input"
OUTPUT_BASE = SEASONALITY_BASE / "output"


# t分布の95%CI用係数 (df → 両側95%の臨界値)
# n-1 のサイズで使う簡易テーブル。30以上は1.96で近似。
T_CRIT_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def t_critical_95(df: int) -> float:
    """両側95%の t 臨界値を返す。df>30 は 1.96 で近似。"""
    if df <= 0:
        return float("nan")
    if df >= 30:
        return 1.96
    return T_CRIT_95.get(df, 1.96)


def safe_round(x: Optional[float], digits: int = 4) -> Optional[float]:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), digits)


def compute_month_stats(returns: list[float]) -> dict:
    """単月の騰落率リストから統計量を計算。"""
    n = len(returns)
    if n == 0:
        return {
            "n": 0, "mean": None, "median": None, "std": None, "se": None,
            "ci95_low": None, "ci95_high": None, "neg_rate": None,
            "mean_median_gap": None, "t_stat": None, "p_value": None,
        }

    mean = sum(returns) / n
    med = median(returns)
    std = stdev(returns) if n >= 2 else 0.0
    se = std / math.sqrt(n) if n >= 2 else 0.0
    t_crit = t_critical_95(n - 1)
    margin = t_crit * se if n >= 2 else 0.0
    neg_rate = sum(1 for r in returns if r < 0) / n

    # 1サンプルt検定: H0: 平均=0, 両側
    if n >= 2 and se > 0:
        t_stat = mean / se
        # 自由度 n-1 の両側p値
        p_value = float(2.0 * scistats.t.sf(abs(t_stat), df=n - 1))
    else:
        t_stat = None
        p_value = None

    return {
        "n": n,
        "mean": safe_round(mean),
        "median": safe_round(med),
        "std": safe_round(std),
        "se": safe_round(se),
        "ci95_low": safe_round(mean - margin),
        "ci95_high": safe_round(mean + margin),
        "neg_rate": safe_round(neg_rate),
        "mean_median_gap": safe_round(mean - med),
        "t_stat": safe_round(t_stat),
        "p_value": safe_round(p_value, 6),
    }


def load_daily_csv(csv_path: Path) -> pd.DataFrame:
    """日足CSVを読み込み、time / open / close と year, month, day を整える。"""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    required = {"time", "open", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").reset_index(drop=True)
    df["year"] = df["time"].dt.year
    df["month"] = df["time"].dt.month
    df["day"] = df["time"].dt.day
    return df


def build_monthly_stats(
    df: pd.DataFrame,
    symbol: str,
    start_year: int,
    end_year: int,
    recent_years: int,
) -> dict:
    """月別統計（full / recent / diff）の JSON 構造を生成。"""
    # 月足リターン: 各年・各月の月初open → 月末close
    monthly = (
        df.groupby(["year", "month"])
        .agg(open_first=("open", "first"), close_last=("close", "last"))
        .reset_index()
    )
    monthly["return_pct"] = (
        (monthly["close_last"] - monthly["open_first"]) / monthly["open_first"] * 100.0
    )

    full = monthly[(monthly["year"] >= start_year) & (monthly["year"] <= end_year)]
    recent_start = end_year - recent_years + 1
    recent = monthly[(monthly["year"] >= recent_start) & (monthly["year"] <= end_year)]

    months_data = []
    for m in range(1, 13):
        full_returns = full.loc[full["month"] == m, "return_pct"].tolist()
        recent_returns = recent.loc[recent["month"] == m, "return_pct"].tolist()

        full_stats = compute_month_stats(full_returns)
        recent_stats = compute_month_stats(recent_returns)

        diff = {
            "mean_diff": (
                safe_round(recent_stats["mean"] - full_stats["mean"])
                if full_stats["mean"] is not None and recent_stats["mean"] is not None
                else None
            ),
            "neg_rate_diff": (
                safe_round(recent_stats["neg_rate"] - full_stats["neg_rate"])
                if full_stats["neg_rate"] is not None and recent_stats["neg_rate"] is not None
                else None
            ),
        }

        months_data.append({
            "month": m,
            "full": full_stats,
            "recent": recent_stats,
            "diff": diff,
        })

    return {
        "symbol": symbol,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "periods": {
            "full": {
                "start_year": start_year,
                "end_year": end_year,
                "label": f"{start_year}-{end_year}",
            },
            "recent": {
                "start_year": recent_start,
                "end_year": end_year,
                "label": f"直近{recent_years}年",
            },
        },
        "months": months_data,
    }


def build_intramonth_path(
    df: pd.DataFrame,
    symbol: str,
    start_year: int,
    end_year: int,
    recent_years: int,
) -> dict:
    """月内累積平均パス。営業日インデックスでアラインメント。

    ロジック:
      各 (年, 月) について、その月の営業日に番号 1..n を振り、
      日次リターン（close - open）/ open を計算、累積和を取る。
      営業日インデックス t に対して、過去年×月の累積リターンを平均する。
    """
    # 日次リターン
    df = df.copy()
    df["daily_return_pct"] = (df["close"] - df["open"]) / df["open"] * 100.0

    # 各 (year, month) 内で営業日番号を振る
    df["trading_day_idx"] = df.groupby(["year", "month"]).cumcount() + 1

    # (year, month) ごとの累積リターン
    df["cum_return_pct"] = df.groupby(["year", "month"])["daily_return_pct"].cumsum()

    full = df[(df["year"] >= start_year) & (df["year"] <= end_year)]
    recent_start = end_year - recent_years + 1
    recent = df[(df["year"] >= recent_start) & (df["year"] <= end_year)]

    def aggregate(subset: pd.DataFrame, month: int) -> dict:
        m_data = subset[subset["month"] == month]
        if m_data.empty:
            return {"trading_days": [], "cum_mean_pct": [], "n_per_day": []}
        # 営業日インデックスごとに累積リターン平均
        # 月によって営業日数が異なるので最大値を取る
        max_days = int(m_data["trading_day_idx"].max())
        trading_days = []
        cum_mean = []
        n_per_day = []
        for t in range(1, max_days + 1):
            day_data = m_data.loc[m_data["trading_day_idx"] == t, "cum_return_pct"]
            n = len(day_data)
            if n == 0:
                continue
            trading_days.append(t)
            cum_mean.append(safe_round(day_data.mean()))
            n_per_day.append(n)
        return {
            "trading_days": trading_days,
            "cum_mean_pct": cum_mean,
            "n_per_day": n_per_day,
        }

    months_data = []
    for m in range(1, 13):
        months_data.append({
            "month": m,
            "full": aggregate(full, m),
            "recent": aggregate(recent, m),
        })

    return {
        "symbol": symbol,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "periods": {
            "full": {
                "start_year": start_year,
                "end_year": end_year,
                "label": f"{start_year}-{end_year}",
            },
            "recent": {
                "start_year": recent_start,
                "end_year": end_year,
                "label": f"直近{recent_years}年",
            },
        },
        "months": months_data,
    }


def build_daily_stats(
    df: pd.DataFrame,
    symbol: str,
    start_year: int,
    end_year: int,
    recent_years: int,
) -> dict:
    """日別ヒートマップ用統計。

    各 (月, 営業日インデックス) について
      - 日次リターン平均 (mean_pct)
      - サンプル数 (n)
      - 下落率 (neg_rate)
    を集計する。
    """
    df = df.copy()
    df["daily_return_pct"] = (df["close"] - df["open"]) / df["open"] * 100.0
    df["trading_day_idx"] = df.groupby(["year", "month"]).cumcount() + 1

    full = df[(df["year"] >= start_year) & (df["year"] <= end_year)]
    recent_start = end_year - recent_years + 1
    recent = df[(df["year"] >= recent_start) & (df["year"] <= end_year)]

    def aggregate_one_month(subset: pd.DataFrame, month: int) -> list[dict]:
        m_data = subset[subset["month"] == month]
        if m_data.empty:
            return []
        max_days = int(m_data["trading_day_idx"].max())
        cells = []
        for t in range(1, max_days + 1):
            day_data = m_data.loc[m_data["trading_day_idx"] == t, "daily_return_pct"]
            n = len(day_data)
            if n == 0:
                continue
            mean_v = float(day_data.mean())
            median_v = float(day_data.median())
            neg_v = float((day_data < 0).mean())
            cells.append({
                "day": t,
                "n": n,
                "mean_pct": safe_round(mean_v),
                "median_pct": safe_round(median_v),
                "neg_rate": safe_round(neg_v),
            })
        return cells

    months_data = []
    for m in range(1, 13):
        months_data.append({
            "month": m,
            "full": aggregate_one_month(full, m),
            "recent": aggregate_one_month(recent, m),
        })

    return {
        "symbol": symbol,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "periods": {
            "full": {
                "start_year": start_year,
                "end_year": end_year,
                "label": f"{start_year}-{end_year}",
            },
            "recent": {
                "start_year": recent_start,
                "end_year": end_year,
                "label": f"直近{recent_years}年",
            },
        },
        "months": months_data,
    }


def write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Seasonality stats JSON builder")
    parser.add_argument("--symbol", "-s", required=True, help="銘柄シンボル (例: SP500)")
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help="日足CSVのパス (省略時は input/{SYMBOL}/{SYMBOL}_1D.csv)",
    )
    parser.add_argument("--start-year", type=int, default=2004, help="分析開始年")
    parser.add_argument("--end-year", type=int, default=2025, help="分析終了年（含む）")
    parser.add_argument("--recent-years", type=int, default=10, help="直近期間の年数")
    args = parser.parse_args()

    symbol = args.symbol
    if args.input:
        csv_path = Path(args.input)
    else:
        csv_path = INPUT_BASE / symbol / f"{symbol}_1D.csv"

    print(f"Loading: {csv_path}")
    df = load_daily_csv(csv_path)
    print(f"  rows: {len(df)}, range: {df['time'].min()} → {df['time'].max()}")

    monthly_stats = build_monthly_stats(
        df, symbol, args.start_year, args.end_year, args.recent_years
    )
    intramonth = build_intramonth_path(
        df, symbol, args.start_year, args.end_year, args.recent_years
    )
    daily_stats = build_daily_stats(
        df, symbol, args.start_year, args.end_year, args.recent_years
    )

    out_dir = OUTPUT_BASE / symbol
    monthly_path = out_dir / "monthly_stats.json"
    intramonth_path = out_dir / "intramonth_path.json"
    daily_path = out_dir / "daily_stats.json"

    write_json(monthly_stats, monthly_path)
    write_json(intramonth, intramonth_path)
    write_json(daily_stats, daily_path)

    print(f"Wrote: {monthly_path}")
    print(f"Wrote: {intramonth_path}")
    print(f"Wrote: {daily_path}")


if __name__ == "__main__":
    main()
