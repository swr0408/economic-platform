# 騰落率分析スクリプト

年に1回の更新用（オンデマンド処理）

## ディレクトリ構成

```
economic-platform/
├── backend/
│   ├── data/
│   │   └── tourakuritsu/
│   │       └── input/              # CSVデータ格納場所
│   │           ├── AUDCAD, 1M.csv  # 月次データ
│   │           └── AUDCAD, 1D.csv  # 日次データ
│   ├── fonts/
│   │   └── NotoSansJP-Regular.ttf  # 日本語フォント
│   └── scripts/
│       └── tourakuritsu/
│           ├── config.py           # 設定ファイル（銘柄名を変更）
│           ├── daily_stats.py      # 月別統計
│           ├── monthly_heatmap.py  # 日別ヒートマップ
│           ├── run_all.py          # 統括実行
│           └── README.md
└── data/
    └── seasonality/                # 出力先（自動生成）
        └── AUDCAD/
            ├── monthly_returns/
            │   └── AUDCAD_Monthly_Statistics_Summary.png
            └── daily_returns/
                ├── 01/
                │   └── AUDCAD_01_Chart.png
                ├── 02/
                └── ...（12まで）
```

## 使用方法

### 簡単な使い方（推奨）

1. `config.py` の `SYMBOL` を変更:
```python
SYMBOL = "AUDCAD"  # ← ここを変更するだけ
```

2. CSVファイルを配置:
```
backend/data/tourakuritsu/input/AUDCAD, 1M.csv
backend/data/tourakuritsu/input/AUDCAD, 1D.csv
```

3. 実行:
```bash
cd backend/scripts/tourakuritsu
python run_all.py
```

4. 出力確認:
```
data/seasonality/AUDCAD/monthly_returns/AUDCAD_Monthly_Statistics_Summary.png
data/seasonality/AUDCAD/daily_returns/01/AUDCAD_01_Chart.png
...
```

### コマンドラインで銘柄を指定

config.pyを変更せずに、コマンドラインで銘柄を指定することも可能:

```bash
python run_all.py --symbol USDJPY
python run_all.py -s TOPIX
```

### 設定確認

現在の設定とパスを確認:
```bash
python config.py
```

出力例:
```
============================================================
騰落率分析スクリプト設定
============================================================

銘柄: AUDCAD

入力ファイル:
  月次: backend/data/tourakuritsu/input/AUDCAD, 1M.csv
  日次: backend/data/tourakuritsu/input/AUDCAD, 1D.csv

出力ディレクトリ:
  月別統計: data/seasonality/AUDCAD/monthly_returns
  日別ヒートマップ: data/seasonality/AUDCAD/daily_returns
```

## 設定ファイル (config.py)

```python
# 銘柄設定（この値を変更するだけで全パスが自動設定）
SYMBOL = "AUDCAD"

# 入力ファイル名のパターン
MONTHLY_FILE_PATTERN = "{symbol}, 1M.csv"
DAILY_FILE_PATTERN = "{symbol}, 1D.csv"
```

## セットアップ

### 1. フォントファイルの配置
日本語フォント（NotoSansJP-Regular.ttf）を `backend/fonts/` に配置。

ダウンロード: https://fonts.google.com/noto/specimen/Noto+Sans+JP

### 2. CSVデータの配置
銘柄データを `backend/data/tourakuritsu/input/` に配置。

CSVファイルの形式:
- 必要カラム: `time`, `open`, `close`
- ファイル名: `{銘柄名}, 1M.csv` / `{銘柄名}, 1D.csv`

## オプション

### run_all.py
| オプション | デフォルト | 説明 |
|-----------|----------|------|
| --symbol, -s | config.pyのSYMBOL | 銘柄名 |
| --monthly-input, -m | 自動設定 | 月次データCSVパス |
| --daily-input, -d | 自動設定 | 日次データCSVパス |
| --skip-monthly | false | 月別統計をスキップ |
| --skip-daily | false | 日別ヒートマップをスキップ |
| --start-year | 2004 | 月別統計の開始年 |
| --end-year | 2024 | 月別統計の終了年 |
| --heatmap-start-year | 2014 | ヒートマップの開始年 |
| --heatmap-end-year | 2025 | ヒートマップの終了年 |

## 出力構造

```
data/seasonality/{SYMBOL}/
├── monthly_returns/
│   └── {SYMBOL}_Monthly_Statistics_Summary.png
└── daily_returns/
    ├── 01/
    │   └── {SYMBOL}_01_Chart.png
    ├── 02/
    │   └── {SYMBOL}_02_Chart.png
    └── ... (12まで)
```
