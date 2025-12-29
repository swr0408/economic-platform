"""
騰落率分析スクリプト設定ファイル

銘柄名を変更するだけで、入力/出力パスが自動的に設定されます。
"""

from pathlib import Path

# =============================================================================
# 銘柄設定（この値を変更するだけで全パスが自動設定されます）
# =============================================================================
SYMBOL = "AUDCAD"

# =============================================================================
# 入力ファイル名のパターン設定
# =============================================================================
# 月次データファイル名（{symbol}は自動置換）
MONTHLY_FILE_PATTERN = "{symbol}, 1M.csv"
# 日次データファイル名（{symbol}は自動置換）
DAILY_FILE_PATTERN = "{symbol}, 1D.csv"

# =============================================================================
# パス設定（通常は変更不要）
# =============================================================================
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent  # economic-platform/

# 入力ディレクトリ
INPUT_DIR = BASE_DIR / 'data' / 'tourakuritsu' / 'input'

# 出力ベースディレクトリ
OUTPUT_BASE_DIR = PROJECT_ROOT / 'data' / 'seasonality'

# フォントディレクトリ
FONT_DIR = BASE_DIR / 'fonts'
DEFAULT_FONT_PATH = FONT_DIR / 'NotoSansJP-Regular.ttf'

# =============================================================================
# 自動生成パス（SYMBOLから自動計算）
# =============================================================================
def get_monthly_input_path(symbol: str = None) -> Path:
    """月次データの入力パスを取得"""
    s = symbol or SYMBOL
    filename = MONTHLY_FILE_PATTERN.format(symbol=s)
    return INPUT_DIR / filename


def get_daily_input_path(symbol: str = None) -> Path:
    """日次データの入力パスを取得"""
    s = symbol or SYMBOL
    filename = DAILY_FILE_PATTERN.format(symbol=s)
    return INPUT_DIR / filename


def get_monthly_output_dir(symbol: str = None) -> Path:
    """月別統計の出力ディレクトリを取得"""
    s = symbol or SYMBOL
    return OUTPUT_BASE_DIR / s / 'monthly_returns'


def get_daily_output_dir(symbol: str = None) -> Path:
    """日別ヒートマップの出力ベースディレクトリを取得"""
    s = symbol or SYMBOL
    return OUTPUT_BASE_DIR / s / 'daily_returns'


# =============================================================================
# 現在の設定を表示
# =============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("騰落率分析スクリプト設定")
    print("=" * 60)
    print(f"\n銘柄: {SYMBOL}")
    print(f"\n入力ファイル:")
    print(f"  月次: {get_monthly_input_path()}")
    print(f"  日次: {get_daily_input_path()}")
    print(f"\n出力ディレクトリ:")
    print(f"  月別統計: {get_monthly_output_dir()}")
    print(f"  日別ヒートマップ: {get_daily_output_dir()}")
    print(f"\nフォント: {DEFAULT_FONT_PATH}")
