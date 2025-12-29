"""
日別騰落率統計スクリプト

CSVファイルから月別の騰落率平均・中央値・下落率を計算し、グラフを生成する
年に1回の手動更新用（オンデマンド処理）

使用方法:
    python daily_stats.py --input <CSVファイルパス> --symbol <銘柄名>

例:
    python daily_stats.py --input ../data/tourakuritsu/input/TSE_DLY_TOPIX_1M.csv --symbol TOPIX
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import argparse
import matplotlib.font_manager as fm
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


def annotate_bars(ax, rects, jp_font):
    """棒グラフに値を表示"""
    for rect in rects:
        height = rect.get_height()
        kwargs = {'fontproperties': jp_font} if jp_font else {}
        ax.annotate(f'{height:.2f}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, **kwargs)


def process_daily_stats(input_file, symbol=None, start_year=2004, end_year=2024, recent_years=10, output_dir=None):
    """
    日別データから月別統計を計算してグラフを生成

    Parameters:
    -----------
    input_file : str
        入力CSVファイルのパス
    symbol : str, optional
        銘柄名（指定しない場合はファイル名から取得）
    start_year : int
        分析開始年
    end_year : int
        分析終了年
    recent_years : int
        直近何年分を比較するか
    output_dir : str, optional
        出力ディレクトリ（指定しない場合は seasonality/{symbol}/ に出力）
    """
    # フォントの読み込み
    jp_font = load_font()

    # CSVファイルの読み込み
    data = pd.read_csv(input_file)

    # 銘柄名の取得
    if symbol is None:
        symbol = os.path.basename(input_file).split(',')[0].replace('_', ' ')

    # ファイル名用のサニタイズされた銘柄名
    safe_symbol = symbol.replace(' ', '_').replace('/', '_')

    # 出力ディレクトリの設定
    # 構造: seasonality/{symbol}/monthly_returns/
    if output_dir is None:
        output_dir = OUTPUT_BASE_DIR / safe_symbol / 'monthly_returns'
    os.makedirs(output_dir, exist_ok=True)

    # 時間列を日付型に変換
    data['time'] = pd.to_datetime(data['time'], utc=True)
    data['year'] = data['time'].dt.year
    data['month'] = data['time'].dt.month

    # 騰落率の計算
    data['rate_of_change'] = ((data['close'] - data['open']) / data['open']) * 100

    # データのフィルタリング
    filtered_data = data[(data['year'] >= start_year) & (data['year'] < end_year)]
    recent_start_year = end_year - recent_years
    last_n_years_data = data[data['year'] >= recent_start_year]

    # 月ラベル
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # 月別統計の計算
    average_changes = []
    medians = []
    negative_proportions = []

    for month in range(1, 13):
        month_data_full = filtered_data[filtered_data['month'] == month]['rate_of_change']
        month_data_recent = last_n_years_data[last_n_years_data['month'] == month]['rate_of_change']

        average_changes.append([month_data_full.mean(), month_data_recent.mean()])
        medians.append([month_data_full.median(), month_data_recent.median()])
        negative_proportions.append([
            (month_data_full < 0).mean() if len(month_data_full) > 0 else 0,
            (month_data_recent < 0).mean() if len(month_data_recent) > 0 else 0
        ])

    # numpy配列に変換
    average_changes = np.array(average_changes)
    medians = np.array(medians)
    negative_proportions = np.array(negative_proportions)

    # グラフの作成
    fig, axs = plt.subplots(3, 1, figsize=(14, 18))

    title = f'騰落率平均・中央値・下落率 {symbol}: {start_year}-{end_year}/直近{recent_years}年'
    if jp_font:
        fig.suptitle(title, fontsize=16, fontproperties=jp_font)
    else:
        fig.suptitle(title, fontsize=16)

    x = np.arange(len(months))

    # 凡例設定
    label_full = f'{start_year}-{end_year}'
    label_recent = f'直近{recent_years}年'
    legend_props = {'prop': jp_font} if jp_font else {}

    # 平均騰落率
    rects1 = axs[0].bar(x - 0.2, average_changes[:, 0], width=0.4, label=label_full, color='blue')
    rects2 = axs[0].bar(x + 0.2, average_changes[:, 1], width=0.4, label=label_recent, color='red')
    if jp_font:
        axs[0].set_title('平均騰落率', fontsize=14, fontproperties=jp_font)
        axs[0].set_ylabel('(%)', fontsize=12, fontproperties=jp_font)
    else:
        axs[0].set_title('Average Rate of Change', fontsize=14)
        axs[0].set_ylabel('(%)', fontsize=12)
    axs[0].set_xticks(x)
    axs[0].set_xticklabels(months, fontsize=10)
    axs[0].legend(fontsize=12, **legend_props)
    annotate_bars(axs[0], rects1, jp_font)
    annotate_bars(axs[0], rects2, jp_font)

    # 中央値
    rects3 = axs[1].bar(x - 0.2, medians[:, 0], width=0.4, label=label_full, color='blue')
    rects4 = axs[1].bar(x + 0.2, medians[:, 1], width=0.4, label=label_recent, color='red')
    if jp_font:
        axs[1].set_title('中央値', fontsize=14, fontproperties=jp_font)
        axs[1].set_ylabel('(%)', fontsize=12, fontproperties=jp_font)
    else:
        axs[1].set_title('Median Rate of Change', fontsize=14)
        axs[1].set_ylabel('(%)', fontsize=12)
    axs[1].set_xticks(x)
    axs[1].set_xticklabels(months, fontsize=10)
    axs[1].legend(fontsize=12, **legend_props)
    annotate_bars(axs[1], rects3, jp_font)
    annotate_bars(axs[1], rects4, jp_font)

    # 下落率
    rects5 = axs[2].bar(x - 0.2, negative_proportions[:, 0], width=0.4, label=label_full, color='blue')
    rects6 = axs[2].bar(x + 0.2, negative_proportions[:, 1], width=0.4, label=label_recent, color='red')
    if jp_font:
        axs[2].set_title('下落率', fontsize=14, fontproperties=jp_font)
        axs[2].set_ylabel('(%)', fontsize=12, fontproperties=jp_font)
    else:
        axs[2].set_title('Negative Rate Proportion', fontsize=14)
        axs[2].set_ylabel('(%)', fontsize=12)
    axs[2].set_xticks(x)
    axs[2].set_xticklabels(months, fontsize=10)
    axs[2].legend(fontsize=12, **legend_props)
    annotate_bars(axs[2], rects5, jp_font)
    annotate_bars(axs[2], rects6, jp_font)

    # レイアウト調整と保存
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    save_path = os.path.join(output_dir, f'{safe_symbol}_Monthly_Statistics_Summary.png')
    plt.savefig(save_path, bbox_inches='tight', dpi=150)
    plt.close()

    print(f'グラフを保存しました: {save_path}')
    return save_path


def main():
    parser = argparse.ArgumentParser(description='日別騰落率統計を計算してグラフを生成')
    parser.add_argument('--input', '-i', type=str, required=True, help='入力CSVファイルのパス')
    parser.add_argument('--symbol', '-s', type=str, help='銘柄名')
    parser.add_argument('--start-year', type=int, default=2004, help='分析開始年 (デフォルト: 2004)')
    parser.add_argument('--end-year', type=int, default=2024, help='分析終了年 (デフォルト: 2024)')
    parser.add_argument('--recent-years', type=int, default=10, help='直近何年分を比較するか (デフォルト: 10)')
    parser.add_argument('--output-dir', '-o', type=str, help='出力ディレクトリ')

    args = parser.parse_args()

    process_daily_stats(
        input_file=args.input,
        symbol=args.symbol,
        start_year=args.start_year,
        end_year=args.end_year,
        recent_years=args.recent_years,
        output_dir=args.output_dir
    )


if __name__ == '__main__':
    main()
