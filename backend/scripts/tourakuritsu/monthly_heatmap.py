"""
月別騰落率ヒートマップスクリプト

日次CSVデータから各月の日別騰落率ヒートマップを生成する
年に1回の手動更新用（オンデマンド処理）

使用方法:
    python monthly_heatmap.py --input <CSVファイルパス> --symbol <銘柄名>

例:
    python monthly_heatmap.py --input ../data/tourakuritsu/input/TSE_DLY_TOPIX_1D.csv --symbol TOPIX
"""

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import io
import chardet
import matplotlib.gridspec as gridspec
import matplotlib.font_manager as fm
import os
import argparse
from pathlib import Path

# スクリプトのディレクトリを基準にパスを解決
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent  # economic-platform/
DATA_DIR = BASE_DIR / 'data' / 'tourakuritsu'
INPUT_DIR = DATA_DIR / 'input'
# 出力先: economic-platform/data/seasonality/{symbol}/
OUTPUT_BASE_DIR = PROJECT_ROOT / 'data' / 'seasonality'
FONT_DIR = BASE_DIR / 'fonts'

# デフォルトのフォントパス
DEFAULT_FONT_PATH = FONT_DIR / 'NotoSansJP-Regular.ttf'


def detect_encoding(file_path):
    """ファイルのエンコーディングを自動判別"""
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']


def load_font(font_path=None):
    """日本語フォントを読み込む"""
    if font_path is None:
        font_path = DEFAULT_FONT_PATH

    if os.path.exists(font_path):
        return fm.FontProperties(fname=str(font_path))
    else:
        print(f"警告: フォントファイルが見つかりません: {font_path}")
        print("デフォルトフォントを使用します")
        return None


def process_monthly_heatmap(input_file, symbol=None, start_year=2014, end_year=2025,
                            recent_years=5, vmin=-2, vmax=2, output_dir=None):
    """
    日次データから月別ヒートマップを生成

    Parameters:
    -----------
    input_file : str
        入力CSVファイルのパス
    symbol : str, optional
        銘柄名（指定しない場合はファイル名から取得）
    start_year : int
        分析開始年
    end_year : int
        分析終了年（含まない）
    recent_years : int
        直近何年分を別途計算するか
    vmin, vmax : float
        ヒートマップのカラースケール範囲
    output_dir : str, optional
        出力ディレクトリ（指定しない場合は seasonality/{symbol}/ に出力）
    """
    # フォントの読み込み
    jp_font = load_font()

    # ファイルのエンコーディングを検出して読み込み
    encoding = detect_encoding(input_file)
    data_bytes = open(input_file, 'rb').read()
    data_text = data_bytes.decode(encoding, errors='replace')
    data = pd.read_csv(io.StringIO(data_text))

    # 時間列を日付型に変換
    data['time'] = pd.to_datetime(data['time'])

    # 銘柄名の取得
    if symbol is None:
        symbol = os.path.basename(input_file).split(',')[0].replace('_', ' ')

    # ファイル名用のサニタイズされた銘柄名
    safe_symbol = symbol.replace(' ', '_').replace('/', '_')

    # 出力ベースディレクトリの設定
    # 構造: seasonality/{symbol}/daily_returns/{月番号}/
    if output_dir is None:
        base_output_dir = OUTPUT_BASE_DIR / safe_symbol / 'daily_returns'
    else:
        base_output_dir = Path(output_dir)

    # 月の名前リスト
    months_jp = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

    output_files = []

    # 各月のヒートマップを生成
    for month_to_process in range(1, 13):
        # 月ごとのディレクトリを作成
        month_output_dir = base_output_dir / f'{month_to_process:02d}'
        os.makedirs(month_output_dir, exist_ok=True)

        monthly_data = data[data['time'].dt.month == month_to_process]

        data_matrix = pd.DataFrame()
        for year in range(start_year, end_year):
            month_year_data = monthly_data[monthly_data['time'].dt.year == year]
            if not month_year_data.empty:
                daily_rate = month_year_data['close'].pct_change() * 100
                data_matrix = pd.concat([data_matrix, daily_rate.reset_index(drop=True)], axis=1)

        if data_matrix.empty:
            print(f"警告: {month_to_process}月のデータが見つかりません")
            continue

        data_matrix.columns = range(start_year, start_year + len(data_matrix.columns))

        # 統計量の計算
        averages = data_matrix.mean(axis=1)
        medians = data_matrix.median(axis=1)
        probabilities = (data_matrix < 0).sum(axis=1) / len(data_matrix.columns) * 100

        # 直近N年間の統計
        last_n_years = data_matrix.iloc[:, -recent_years:] if len(data_matrix.columns) >= recent_years else data_matrix
        last_n_years_avg = last_n_years.mean(axis=1)
        last_n_years_median = last_n_years.median(axis=1)
        last_n_years_prob = (last_n_years < 0).sum(axis=1) / min(recent_years, len(last_n_years.columns)) * 100

        # 統計量を追加したDataFrameを作成
        data_with_stats = pd.concat([
            data_matrix,
            averages, medians, probabilities,
            last_n_years_avg, last_n_years_median, last_n_years_prob
        ], axis=1)
        data_with_stats.columns = (
            [str(year) for year in data_matrix.columns] +
            ['Avg', 'Med', 'Prob', f'Last {recent_years}Yr Avg', f'Last {recent_years}Yr Med', f'Last {recent_years}Yr Prob']
        )

        # プロットの作成
        plt.figure(figsize=(18, 10))
        gs = gridspec.GridSpec(1, 2, width_ratios=[len(data_matrix.columns) + 4, 2])

        # メインヒートマップ用データ
        combined_data = pd.concat([
            data_matrix,
            averages, medians, last_n_years_avg, last_n_years_median
        ], axis=1)

        # メインヒートマップ
        plt.subplot(gs[0])
        ax1 = sns.heatmap(
            combined_data.iloc[1:],
            cmap='coolwarm_r',
            center=0,
            annot=True,
            fmt=".2f",
            cbar=False,
            vmin=vmin,
            vmax=vmax
        )

        title = f'{months_jp[month_to_process - 1]} 騰落率平均/中央値・下落率 {start_year}-{end_year-1} - {symbol}'
        if jp_font:
            plt.title(title, fontproperties=jp_font)
            plt.ylabel('', fontproperties=jp_font)
        else:
            plt.title(title)
            plt.ylabel('')

        # 確率ヒートマップ
        plt.subplot(gs[1])
        prob_data = data_with_stats[['Prob', f'Last {recent_years}Yr Prob']].iloc[1:]
        ax2 = sns.heatmap(
            prob_data,
            cmap='coolwarm',
            center=50,
            annot=True,
            fmt=".2f",
            cbar=False
        )
        if jp_font:
            plt.ylabel('', fontproperties=jp_font)
        else:
            plt.ylabel('')

        # X軸ラベルの設定
        x_labels_main = [str(year) for year in data_matrix.columns] + ['平均', '中央値', f'平均(直近{recent_years}年)', f'中央値(直近{recent_years}年)']
        x_labels_prob = ['下落率', f'下落率(直近{recent_years}年)']

        if jp_font:
            ax1.set_xticklabels(x_labels_main, rotation=45, horizontalalignment='right', fontproperties=jp_font)
            ax2.set_xticklabels(x_labels_prob, rotation=45, horizontalalignment='right', fontproperties=jp_font)
        else:
            ax1.set_xticklabels(x_labels_main, rotation=45, horizontalalignment='right')
            ax2.set_xticklabels(x_labels_prob, rotation=45, horizontalalignment='right')

        # 保存（月ごとのディレクトリに出力）
        output_file = os.path.join(month_output_dir, f'{safe_symbol}_{month_to_process:02d}_Chart.png')
        plt.savefig(output_file, bbox_inches='tight', dpi=150)
        plt.close()

        output_files.append(output_file)
        print(f'グラフを保存しました: {output_file}')

    return output_files


def main():
    parser = argparse.ArgumentParser(description='月別騰落率ヒートマップを生成')
    parser.add_argument('--input', '-i', type=str, required=True, help='入力CSVファイルのパス')
    parser.add_argument('--symbol', '-s', type=str, help='銘柄名')
    parser.add_argument('--start-year', type=int, default=2014, help='分析開始年 (デフォルト: 2014)')
    parser.add_argument('--end-year', type=int, default=2025, help='分析終了年 (デフォルト: 2025)')
    parser.add_argument('--recent-years', type=int, default=5, help='直近何年分を比較するか (デフォルト: 5)')
    parser.add_argument('--vmin', type=float, default=-2.0, help='ヒートマップの最小値 (デフォルト: -2.0)')
    parser.add_argument('--vmax', type=float, default=2.0, help='ヒートマップの最大値 (デフォルト: 2.0)')
    parser.add_argument('--output-dir', '-o', type=str, help='出力ディレクトリ')

    args = parser.parse_args()

    process_monthly_heatmap(
        input_file=args.input,
        symbol=args.symbol,
        start_year=args.start_year,
        end_year=args.end_year,
        recent_years=args.recent_years,
        vmin=args.vmin,
        vmax=args.vmax,
        output_dir=args.output_dir
    )


if __name__ == '__main__':
    main()
