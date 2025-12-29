"""
統括実行スクリプト

config.py の SYMBOL を変更するだけで、自動的に適切なパスで実行されます。

使用方法:
    1. config.py の SYMBOL を変更
    2. python run_all.py を実行

または、コマンドラインで銘柄を指定:
    python run_all.py --symbol AUDCAD
"""

import subprocess
import sys
import argparse
from pathlib import Path

# 設定ファイルからインポート
from config import (
    SYMBOL,
    get_monthly_input_path,
    get_daily_input_path,
)

SCRIPT_DIR = Path(__file__).parent


def run_script(script_name, args):
    """サブスクリプトを実行"""
    script_path = SCRIPT_DIR / script_name
    cmd = [sys.executable, str(script_path)] + args

    print(f"\n{'='*60}")
    print(f"実行中: {script_name}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✓ {script_name} 完了")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {script_name} エラー: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='騰落率分析を一括実行')
    parser.add_argument('--symbol', '-s', type=str, default=SYMBOL,
                        help=f'銘柄名 (デフォルト: config.pyのSYMBOL={SYMBOL})')
    parser.add_argument('--monthly-input', '-m', type=str,
                        help='月次データCSVファイルのパス（指定しない場合は自動設定）')
    parser.add_argument('--daily-input', '-d', type=str,
                        help='日次データCSVファイルのパス（指定しない場合は自動設定）')

    # 日別統計用パラメータ
    parser.add_argument('--start-year', type=int, default=2004, help='日別統計の分析開始年')
    parser.add_argument('--end-year', type=int, default=2024, help='日別統計の分析終了年')
    parser.add_argument('--recent-years', type=int, default=10, help='日別統計の直近年数')

    # ヒートマップ用パラメータ
    parser.add_argument('--heatmap-start-year', type=int, default=2014, help='ヒートマップの分析開始年')
    parser.add_argument('--heatmap-end-year', type=int, default=2025, help='ヒートマップの分析終了年')
    parser.add_argument('--heatmap-recent-years', type=int, default=5, help='ヒートマップの直近年数')
    parser.add_argument('--vmin', type=float, default=-2.0, help='ヒートマップの最小値')
    parser.add_argument('--vmax', type=float, default=2.0, help='ヒートマップの最大値')

    # スキップオプション
    parser.add_argument('--skip-monthly', action='store_true', help='月別統計をスキップ')
    parser.add_argument('--skip-daily', action='store_true', help='日別ヒートマップをスキップ')

    args = parser.parse_args()

    # 銘柄名
    symbol = args.symbol

    # 入力パスの決定（指定がなければ自動設定）
    monthly_input = args.monthly_input or str(get_monthly_input_path(symbol))
    daily_input = args.daily_input or str(get_daily_input_path(symbol))

    print("=" * 60)
    print(f"騰落率分析: {symbol}")
    print("=" * 60)
    print(f"月次データ: {monthly_input}")
    print(f"日次データ: {daily_input}")

    results = []

    # 月別統計の実行
    if not args.skip_monthly:
        daily_args = [
            '--input', monthly_input,
            '--symbol', symbol,
            '--start-year', str(args.start_year),
            '--end-year', str(args.end_year),
            '--recent-years', str(args.recent_years),
        ]
        results.append(('daily_stats.py', run_script('daily_stats.py', daily_args)))

    # 日別ヒートマップの実行
    if not args.skip_daily:
        heatmap_args = [
            '--input', daily_input,
            '--symbol', symbol,
            '--start-year', str(args.heatmap_start_year),
            '--end-year', str(args.heatmap_end_year),
            '--recent-years', str(args.heatmap_recent_years),
            '--vmin', str(args.vmin),
            '--vmax', str(args.vmax),
        ]
        results.append(('monthly_heatmap.py', run_script('monthly_heatmap.py', heatmap_args)))

    # 結果サマリー
    print(f"\n{'='*60}")
    print("実行結果サマリー")
    print(f"{'='*60}")

    all_success = True
    for script_name, success in results:
        status = "✓ 成功" if success else "✗ 失敗"
        print(f"  {script_name}: {status}")
        if not success:
            all_success = False

    if all_success and results:
        print(f"\n全ての処理が正常に完了しました。")
        print(f"出力先: data/seasonality/{symbol}/")
    elif not results:
        print("\n処理がスキップされました。")
    else:
        print("\n一部の処理でエラーが発生しました。")
        sys.exit(1)


if __name__ == '__main__':
    main()
