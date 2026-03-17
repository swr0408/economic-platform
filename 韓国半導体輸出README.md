# 韓国半導体輸出データ スクレイパー

MOTIE（産業通商資源部）の月次レポートから韓国半導体輸出データを自動取得するモジュール。

## データソース

| レポート | 公開タイミング | 内容 | 用途 |
|---|---|---|---|
| **수출입 동향**（輸出入動向） | 毎月1日 | 半導体ヘッドライン値（金額+YoY） | 速報値 |
| **ICT 수출입 동향**（ICT輸出入動向） | 毎月12〜15日 | 品目別詳細テーブル（13ヶ月ローリング） | 詳細値+時系列 |

どちらも MOTIE + MSIT（科学技術情報通信部）が共同発表する公式統計。
`motir.go.kr`（旧 motie.go.kr）の報道資料ページで公開される。

## ファイル構成

```
kr_semiconductor_scraper/
├── scraper.py       # コアモジュール（パーサー + Playwright スクレイパー）
├── backfill.py      # 初期シードデータ + 過去記事バックフィル
├── scheduler.py     # APScheduler連携 + DBスキーマ + FastAPIエンドポイント例
├── test_parser.py   # パーサーのユニットテスト
└── README.md
```

## セットアップ

```bash
pip install playwright beautifulsoup4
playwright install chromium
```

## 使い方

### 1. パーサーテスト実行

```bash
python test_parser.py
```

### 2. シードデータ投入（オフライン・MOTIEアクセス不要）

```bash
python backfill.py --seed-only
```

検索結果・報道から確認済みの実データ（2026年1-2月 + 年間合計）をJSONに出力。

### 3. MOTIEから最新レポート取得

```bash
python scraper.py
```

Playwright で MOTIE サイトにアクセスし、최신の수출입 동향 + ICT 수출입 동향を取得。

### 4. 過去記事バックフィル

```bash
python backfill.py --scrape --pages 3
```

ICT レポートの過去記事を遡ってクロール。
各レポートに13ヶ月ローリングテーブルが含まれるため、3本で約2〜3年分の時系列が構築可能。

### 5. APScheduler への組み込み

```python
from apscheduler.schedulers.background import BackgroundScheduler
from scheduler import register_kr_semiconductor_jobs

scheduler = BackgroundScheduler()
register_kr_semiconductor_jobs(scheduler, db_save_func=your_save_func)
scheduler.start()
```

## スケジュール

| ジョブ | タイミング | 説明 |
|---|---|---|
| Trade Report | 毎月2〜5日 09:00 KST | 수출입 동향から速報値取得 |
| ICT Report | 毎月13〜18日 10:00 KST | ICT 수출입 동향から詳細値取得 |

## DBスキーマ

```sql
CREATE TABLE kr_semiconductor_exports (
    id                BIGSERIAL PRIMARY KEY,
    ref_month         VARCHAR(7) NOT NULL UNIQUE,  -- "2025-03"
    value_usd_billion NUMERIC(10,3),               -- 10億ドル
    yoy_pct           NUMERIC(8,2),                -- 前年同月比 %
    source_report     VARCHAR(20) NOT NULL,         -- "TRADE" / "ICT"
    published_at      VARCHAR(20),
    source_url        TEXT,
    raw_text          TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);
```

## パーサーが対応するテキストパターン

### 수출입 동향（韓国語）
- `반도체 수출은 131억 달러(+11.9%)`
- `반도체(252억 달러, 160.9%↑)`
- `반도체 수출은 72억 달러(△36.2%)`

### 수출입 동향（英語）
- `Semiconductor exports rose to $13.1 billion (up 11.9 percent)`
- `Semiconductor exports fell to $4.8 billion (down 44.5 percent)`

### ICT 수출입 동향 トレンドテーブル
```
구분   '24.10  11    12   '25.1   2     3    ...
반도체 140.9  142.1 165.3 162.7  165.4 188.1 ...
       (42.5)(22.0)(24.2)(-0.5) (0.2)(19.3) ...
```

### ICT 수출입 동향 インライン記述
- `반도체 수출이 102.7% 증가하며 205억 5000만 달러`
- `반도체(205.5억 달러, 102.7%↑)`

## 注意事項

- MOTIE の「半導体」は政策カテゴリであり、関税庁 HS コード（8541/8542）とは完全一致しない
- `motir.go.kr` は robots.txt で一部制限あり → Playwright によるブラウザアクセスが必要
- ICT レポートの詳細テーブルが添付 PDF にのみ含まれる場合、本文パースでは取得不可
  （その場合は添付ファイル情報をエラーに記録する）
- 単位変換: MOTIE の「億ドル」(100M USD) → DB では「10億ドル」(1B USD) に統一

## 確認済みデータ（2026年3月時点）

| 月 | 半導体輸出 | YoY | ソース |
|---|---|---|---|
| 2026-02 | $25.2B | +160.9% | MOTIE 수출입 동향 |
| 2026-01 | $20.55B | +102.7% | MSIT ICT 수출입 동향 |
| 2025年計 | $173.4B | +22.2% | MOTIE 英語版年間報告 |
| 2024年計 | $142.1B | +42.5% | KITA / ICT レポート |
