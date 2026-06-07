"""
Seasonality Stats Builder (一括実行ラッパー)

input/ 配下の全銘柄フォルダを走査し、各銘柄の日足CSVを自動検出して
build_stats.py の処理（monthly_stats / intramonth_path / daily_stats）を
一括で再生成する。

CSV 名は銘柄ごとに異なる（FX_USDJPY, 1D.csv / TVC_DXY, 1D.csv / S&P500_1D.csv 等）
ため、フォルダ内から *1D*.csv パターンで自動検出する。

使用方法:
  python build_stats_all.py
  python build_stats_all.py --end-year 2025
  python build_stats_all.py --only USDJPY,S&P500
  python build_stats_all.py --skip TOPIX
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
INPUT_BASE = BACKEND_DIR / "data" / "manual_update" / "seasonality" / "input"
BUILD_STATS = SCRIPT_DIR / "build_stats.py"


def find_daily_csv(symbol_dir: Path) -> Path | None:
    """銘柄フォルダ内から日足CSV (1D) を探す。

    優先順:
      1. {SYMBOL}_1D.csv (build_stats.py のデフォルトパターン)
      2. *, 1D.csv (TradingView エクスポート形式)
      3. *1D*.csv (フォールバック)
    """
    symbol = symbol_dir.name
    candidates = [
        symbol_dir / f"{symbol}_1D.csv",
    ]
    for c in candidates:
        if c.exists():
            return c

    tv_matches = sorted(symbol_dir.glob("*, 1D.csv"))
    if tv_matches:
        return tv_matches[0]

    fallback = [
        p for p in sorted(symbol_dir.glob("*1D*.csv"))
        if "1M" not in p.name
    ]
    if fallback:
        return fallback[0]

    return None


def run_one(symbol: str, csv_path: Path, start_year: int, end_year: int,
            recent_years: int) -> bool:
    cmd = [
        sys.executable, str(BUILD_STATS),
        "--symbol", symbol,
        "--input", str(csv_path),
        "--start-year", str(start_year),
        "--end-year", str(end_year),
        "--recent-years", str(recent_years),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=False)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [ERROR] {symbol}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Seasonality stats を全銘柄一括再生成")
    parser.add_argument("--start-year", type=int, default=2004, help="分析開始年")
    parser.add_argument("--end-year", type=int, default=2025, help="分析終了年（含む）")
    parser.add_argument("--recent-years", type=int, default=10, help="直近期間の年数")
    parser.add_argument("--only", type=str, default=None,
                        help="特定銘柄のみ実行（カンマ区切り）")
    parser.add_argument("--skip", type=str, default=None,
                        help="スキップする銘柄（カンマ区切り）")
    parser.add_argument("--dry-run", action="store_true",
                        help="検出のみ実行（生成しない）")
    args = parser.parse_args()

    if not INPUT_BASE.exists():
        print(f"Input base not found: {INPUT_BASE}")
        sys.exit(1)

    only_set = {s.strip() for s in args.only.split(",")} if args.only else None
    skip_set = {s.strip() for s in args.skip.split(",")} if args.skip else set()

    symbols = sorted(p.name for p in INPUT_BASE.iterdir() if p.is_dir())

    print("=" * 70)
    print(f"Seasonality Stats 一括再生成")
    print(f"  期間: {args.start_year}-{args.end_year} / 直近{args.recent_years}年")
    print(f"  対象: {len(symbols)}銘柄")
    print("=" * 70)

    results = {"ok": [], "ng": [], "skip": [], "missing": []}

    for sym in symbols:
        if only_set is not None and sym not in only_set:
            results["skip"].append(sym)
            continue
        if sym in skip_set:
            results["skip"].append(sym)
            continue

        symbol_dir = INPUT_BASE / sym
        csv_path = find_daily_csv(symbol_dir)
        if csv_path is None:
            print(f"[SKIP] {sym}: 日足CSVが見つかりません")
            results["missing"].append(sym)
            continue

        print(f"\n[{sym}] {csv_path.name}")
        if args.dry_run:
            results["ok"].append(sym)
            continue

        ok = run_one(sym, csv_path, args.start_year, args.end_year, args.recent_years)
        if ok:
            results["ok"].append(sym)
        else:
            results["ng"].append(sym)

    print("\n" + "=" * 70)
    print("実行サマリー")
    print("=" * 70)
    print(f"  成功:     {len(results['ok'])}")
    print(f"  失敗:     {len(results['ng'])}")
    print(f"  スキップ: {len(results['skip'])}")
    print(f"  CSV不在:  {len(results['missing'])}")
    if results["ng"]:
        print(f"\n  失敗銘柄: {', '.join(results['ng'])}")
    if results["missing"]:
        print(f"\n  CSV不在:  {', '.join(results['missing'])}")

    sys.exit(0 if not results["ng"] else 1)


if __name__ == "__main__":
    main()
