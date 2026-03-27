# 手動更新指標ガイド

手動で更新が必要な指標の一覧です。
各指標のファイルを所定のフォルダに配置すると、サービスが自動検知してデータを更新します。

---

## 日次更新 (`daily/`)

### 北京PM2.5濃度
- **フォルダ**: `daily/beijing_pm25/`
- **ファイル**: `beijing-air-quality.csv`
- **取得元**: https://aqicn.org/city/beijing/
- **形式**: CSV (date, pm25, pm10, o3, no2, so2, co)
- **手順**: CSVファイルを上書き更新

### エコノミックサプライズ指数（スクリーンショット）
- **フォルダ**: `daily/economic_surprise/`
- **ファイル名**:
  - `エコノミックサプライズ指数（global）.png`
  - `エコノミックサプライズ指数（japan）.png`
  - `エコノミックサプライズ指数（china）.png`
- **取得元**:
  - Global: https://en.macromicro.me/charts/45866/global-citi-surprise-index
  - Japan: https://en.macromicro.me/charts/55983/japan-citi-surprise-index-earning
  - China: https://en.macromicro.me/charts/55758/cn-citi-surprise-index-earning
- **手順**: 各ページのチャートをスクリーンショットし、上記ファイル名で保存

### 株式PER（予想PER）
- **フォルダ**: `daily/stock_pe/`
- **ファイル名**:
  - `sp500_pe.csv` — S&P 500 Forward PE
  - `nasdaq100_pe.csv` — NASDAQ-100 PE（月次手動）
  - `nikkei225_per.csv` — 日経平均PER（日次手動）
  - `topix_pe.csv` — TOPIX PE（月次手動）
- **取得元**:
  - S&P 500: https://en.macromicro.me/series/20052/sp500-forward-pe-ratio
  - NASDAQ-100: https://en.macromicro.me/series/23955/nasdaq-100-pe
  - 日経平均: https://indexes.nikkei.co.jp/en/nkave/archives/data?list=per
  - TOPIX: https://en.macromicro.me/charts/95007/japan-nikkei225
- **代替取得先（課金要）**:
  - https://birinyi.com/
  - https://www.wsj.com/market-data/stocks/peyields
- **手順**: データをCSVにエクスポートし上書き保存

---

## 月次更新 (`monthly/`)

### RICS住宅価格バランス（イギリス）
- **フォルダ**: `monthly/uk_rics/`
- **ファイル名**: `YYYYMM-rics-house-price.pdf`（例: `202603-rics-house-price.pdf`）
  - または `rics_residential_survey_YYYYMM.pdf`
- **取得元**: https://www.rics.org/news-insights/market-surveys/uk-residential-market-survey#tabs-6ce14f14d2-item-d25c05351f-tab
- **手順**: PDFをダウンロードしてファイル名を変更して配置

### ハリファックス住宅価格指数（イギリス）
- **フォルダ**: `monthly/uk_halifax/`
- **ファイル名**: `YYYYMMDD-halifax-house-price-index.pdf`（例: `20260306-halifax-house-price-index.pdf`）
- **取得元**: https://www.halifax.co.uk/media-centre/house-price-index.html
- **手順**: PDFをダウンロードしてファイル名を変更して配置

### ライトムーブ住宅価格指数（イギリス）
- **フォルダ**: `monthly/uk_rightmove/`
- **ファイル名**: `Rightmove-HPI-YYYYMMDD.pdf`（例: `Rightmove-HPI-20260316.pdf`）
- **取得元**: https://www.rightmove.co.uk/news/house-price-index/
- **手順**: PDFをダウンロードしてファイル名を変更して配置

### NAB企業信頼感指数（オーストラリア）
- **フォルダ**: `monthly/australia_nab/`
- **ファイル名**: `NAB-Monthly-Business-Survey-YYYYMMDD.pdf`（例: `NAB-Monthly-Business-Survey-20260309.pdf`）
- **抽出項目**: Chart 18（仕入れコスト、雇用コスト）、Chart 20（販売価格、製品価格）
- **取得元**:
  - https://news.nab.com.au/tag/economic-market
  - https://www.mtsinsights.com/events/4205/
- **手順**: PDFをダウンロードしてファイル名を変更して配置

### ISM製造業・非製造業構成指数（Components）
- **フォルダ**: `monthly/ism_components/`
- **ファイル名**:
  - `ism_manufacturing_components.csv` — ISM製造業構成指数（6項目）
  - `ism_non_manufacturing_components.csv` — ISM非製造業構成指数（6項目）
- **取得元**: https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/
- **形式**:
  - 製造業: CSV (date, new_orders, production, employment, supplier_deliveries, prices, inventories)
  - 非製造業: CSV (date, new_orders, business_activity, employment, supplier_deliveries, prices, inventories)
- **日付形式**: YYYY/M（例: 2026/1）
- **更新タイミング**: 製造業は月初第1営業日、非製造業は第3営業日
- **手順**: DBnomicsが更新されていない月のデータを手動で追記。空欄フィールドはFMP DB/DBnomicsの既存値を保持。
- **備考**: DBnomicsが復旧すれば手動更新は不要。FMP DBにある項目（New Orders, Employment, Prices、非製造業はBusiness Activityも）は自動補完されるため、手動更新が必須なのはProduction（製造業のみ）, Supplier Deliveries, Inventoriesの3項目。

### グローバル製造業PMI
- **フォルダ**: `monthly/global_pmi/`
- **ファイル**: `J.P.Morgan Global Manufacturing PMI.csv`
- **更新タイミング**: 月初
- **取得元**:
  - https://www.pmi.spglobal.com/Public/Release/PressReleases?language=en
  - https://stock-marketdata.com/pmi-global-manufacturing.html
- **手順**: 最新月の値をCSVに追記

### OPECレポート（MOMR）
- **フォルダ**: `monthly/opec/`
- **ファイル名**: `momr-appendix-{month}-{year}.xlsx`（例: `momr-appendix-march-2026.xlsx`）
- **取得元**: https://publications.opec.org/momr/Home
- **手順**: Appendix Excelをダウンロードして配置

### IEAレポート（原油市場報告）
- **フォルダ**: `monthly/iea/`
- **ファイル**: `IEA Oil Market Report.csv`
- **取得元**:
  - https://www.iea.org/analysis?type=report&q=oil%20market%20report
  - https://docs.google.com/spreadsheets/d/1e6sGQ5FtEYjnW30ozAb3eb_ppOXqdeR7TpBqgH6RNdw/edit?gid=267427925#gid=267427925
- **手順**: CSVを手動編集して上書き保存

### SNBカレンダー（スイス）
- **フォルダ**: `monthly/switzerland_snb/`
- **ファイル名**:
  - `snb_calendar_YYYY.ics`（Website Calendar — 自動取得あり）
  - `data_snb_ch_calendar_YYYY.en.ics`（Data Portal Calendar — 手動DL）
- **取得元**: https://www.snb.ch/en/services-events/digital-services/rss-calendar-feeds#t01
- **更新タイミング**: 年1回（ICSファイルの手動DLは年初に実施）
- **手順**: ICSファイルをダウンロードして配置

---

## 年次更新 (`yearly/`)

### 中国資本フロースケジュール
- **フォルダ**: `yearly/china_capital_flows/`
- **ファイル名**: `中国資本フロースケジュールYYYY.pdf`（例: `中国資本フロースケジュール2026.pdf`）
- **更新タイミング**: 年末年始
- **取得元（2026年版）**: https://www.safe.gov.cn/safe/file/file/20260113/3eae723de19f4c27a42cf1b6d73057c0.pdf
- **手順**: PDFをダウンロードし、ファイル名を `中国資本フロースケジュールYYYY.pdf` に変更して配置

---

## ディレクトリ構成一覧

```
backend/data/manual_update/
├── MANUAL_UPDATE_GUIDE.md          ← このファイル
├── daily/
│   ├── beijing_pm25/               # 北京PM2.5 CSV
│   ├── economic_surprise/          # エコノミックサプライズ指数 PNG ×3
│   └── stock_pe/                   # S&P500, NASDAQ100, 日経, TOPIX PER CSV
├── monthly/
│   ├── ism_components/              # ISM構成指数 CSV ×2
│   ├── uk_rics/                    # RICS住宅価格 PDF
│   ├── uk_halifax/                 # ハリファックス住宅価格 PDF
│   ├── uk_rightmove/               # ライトムーブ住宅価格 PDF
│   ├── australia_nab/              # NAB企業信頼感 PDF
│   ├── global_pmi/                 # グローバル製造業PMI CSV
│   ├── opec/                       # OPEC MOMR Excel
│   ├── iea/                        # IEA原油市場レポート CSV
│   └── switzerland_snb/            # SNBカレンダー ICS
└── yearly/
    └── china_capital_flows/        # 中国資本フロースケジュール PDF
```
