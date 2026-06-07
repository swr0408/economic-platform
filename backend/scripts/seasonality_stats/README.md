# Seasonality Stats Builder

季節性ページ用の統計 JSON を生成するバッチスクリプト。年に1回ほどの手動更新を想定。

## ディレクトリ構成

```
backend/data/manual_update/seasonality/
├── input/
│   └── {SYMBOL}/
│       └── {SYMBOL}_1D.csv      # 日足CSV (time, open, high, low, close)
└── output/
    └── {SYMBOL}/
        ├── monthly_stats.json    # 月別統計（n, mean, median, std, CI95, neg_rate, diff）
        └── intramonth_path.json  # 月内累積平均パス
```

## 使い方

```bash
cd backend/scripts/seasonality_stats
python build_stats.py --symbol SP500
```

オプション:
- `--symbol, -s`  銘柄シンボル（必須）
- `--input, -i`   CSVパス（省略時は input/{SYMBOL}/{SYMBOL}_1D.csv）
- `--start-year`  分析開始年（デフォルト: 2004）
- `--end-year`    分析終了年（デフォルト: 2025、含む）
- `--recent-years` 直近期間の年数（デフォルト: 10）

## CSV形式

TradingView エクスポート想定。必要カラム:
- `time`  日付
- `open`  始値
- `close` 終値

`high`, `low` は使用しないが含まれていてもよい。

## 出力JSON仕様

### monthly_stats.json
```json
{
  "symbol": "SP500",
  "generated_at": "ISO8601",
  "periods": {
    "full":   { "start_year": 2004, "end_year": 2025, "label": "2004-2025" },
    "recent": { "start_year": 2016, "end_year": 2025, "label": "直近10年" }
  },
  "months": [
    {
      "month": 1,
      "full":   { "n": 21, "mean": ..., "median": ..., "std": ..., "se": ..., "ci95_low": ..., "ci95_high": ..., "neg_rate": ..., "mean_median_gap": ... },
      "recent": { ... },
      "diff":   { "mean_diff": ..., "neg_rate_diff": ... }
    }
  ]
}
```

### intramonth_path.json
```json
{
  "symbol": "SP500",
  "generated_at": "ISO8601",
  "periods": { ... },
  "months": [
    {
      "month": 1,
      "full":   { "trading_days": [1,2,..,21], "cum_mean_pct": [...], "n_per_day": [...] },
      "recent": { ... }
    }
  ]
}
```

`trading_days` はカレンダー日ではなく月初からの**営業日インデックス**。
`cum_mean_pct` は各営業日 t までの累積リターンを年×月で平均したもの（%）。
`n_per_day` は集計に使ったサンプル数（その営業日インデックスを持つ月の数）。
