---
name: add-indicator
description: "新規経済指標を追加する。FMPマッピング、バックエンド、フロントエンド、データ比較機能を含む完全実装"
argument-hint: "[入力フォーム形式で指定]"
disable-model-invocation: false
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
---

# 新規経済指標追加スキル

このスキルは経済指標を追加する際の**完全なチェックリスト**です。
実装漏れを防ぐため、すべてのステップを順番に確認してください。

---

## 入力フォーム

スキル実行時に以下の形式で情報を提供してください：

```yaml
# ===== 基本情報 =====
country: switzerland          # 国名（小文字）: usa, japan, eurozone, uk, switzerland
category: employment          # カテゴリ: economy, employment, inflation, consumer, policy, housing
indicator_name_ja: 失業率      # 指標名（日本語）
indicator_name_en: Unemployment Rate  # 指標名（英語）
pascal_case: CHUnemploymentRate       # PascalCase（クラス名・コンポーネント名用）
snake_case: ch_unemployment_rate      # snake_case（ファイル名・API用）
econalpha_id: ch_unemployment_rate    # ECONALPHA_ID（FMPマッピング用）

# ===== データソース =====
data_source_type: api         # データソース種別: api, db, scraping, excel
data_source_url: "https://example.com/api"  # データソースURL
data_source_name: "BFS (Federal Statistical Office)"  # データソース名

# ===== FMPマッピング =====
fmp_country: CH               # FMP国コード: US, JP, EU, GB, CH
fmp_event_pattern: "Unemployment Rate"  # FMPイベント名（部分一致パターン）。FMPにイベントがない場合は "なし"
fmp_mapping_registered: true  # indicator_event_mapping登録済みか。"なし"の場合はfalse
# 注意: fmp_event_patternが"なし"の場合:
#   - マーケットインパクトタブは追加しない（発表履歴を取得できないため）
#   - 次回発表日は独自実装が必要（RSSフィード解析、スクレイピング等）

# ===== 発表スケジュール =====
frequency: monthly            # 頻度: daily, weekly, monthly, quarterly, yearly, irregular
release_pattern: "毎月上旬"    # 発表パターン説明

# ===== 表示形式 =====
display_yoy: false            # 前年比表示
display_mom: false            # 前月比表示
display_qoq: false            # 前期比表示（四半期指標の場合）
display_raw: true             # 原数値表示
chart_type: line              # グラフ種別: line, bar, area
y_axis_format: number         # Y軸フォーマット: number, percent, index
chart_color: "#DC143C"        # グラフ色（省略可）
unit: "%"                     # 単位

# ===== テーブル表示 =====
# 注意: テーブル表示は基本的に使用しない（他指標との統一性のため）
# 特別な理由がない限り show_table: false を推奨
show_table: false             # テーブル表示するか（基本はfalse）
table_type: none              # テーブル種別: none, monthly, quarterly

# ===== 系列数 =====
series_count: single          # 系列数: single, multiple

# ===== データ比較機能 =====
add_to_overlay: true          # overlayConfigに追加するか
overlay_sub_category: jobs    # サブカテゴリ: gdp, sentiment, jobs, wages, cpi, etc.
compare_button_targets:       # 比較ボタン初期選択（最大6個）
  - ch_unemployment_rate

# ===== 特記事項 =====
notes: |
  各年でシートが分かれている
  毎回更新日にそれぞれのシートから取得し時系列データにする
```

---

## 実装チェックリスト

### Phase 1: バックエンド実装

#### 1.1 サービスファイル作成
- [ ] **ファイル**: `backend/services/{country}/{snake_case}_service.py`
- [ ] テンプレート: [templates/service.py.md](templates/service.py.md) を参照
- [ ] 必須実装:
  - [ ] `get_{snake_case}_data()` メソッド
  - [ ] `_load_from_*()` データ取得メソッド（API/DB/Excel等）
  - [ ] `_should_refresh()` キャッシュ更新判定
  - [ ] Redisキャッシュ（`{country}:{snake_case}:data`）
  - [ ] ファイルキャッシュ（フォールバック用）
  - [ ] `next_release` 取得
  - [ ] シングルトンインスタンス

#### 1.2 ダッシュボードローダー更新
- [ ] **ファイル**: `backend/services/dashboard/loaders/{country}_{category}.py`
- [ ] `EXPECTED_KEYS` に `{snake_case}` を追加
- [ ] `load_all()` に取得処理を追加
- [ ] `_get_{snake_case}()` ヘルパーメソッド追加

#### 1.3 レジストリ確認
- [ ] **ファイル**: `backend/services/dashboard/registry.py`
- [ ] ローダーが登録されていることを確認

#### 1.4 FMPマッピング確認（未登録の場合）
- [ ] **ファイル**: `backend/scripts/add_indicator_mappings.sql`
- [ ] indicator_event_mapping テーブルにレコード追加

---

### Phase 2: フロントエンド実装

#### 2.1 型定義追加
- [ ] **ファイル**: `frontend/src/hooks/useDashboardData.ts`
- [ ] データ型インターフェース追加（例: `{PascalCase}Data`）
- [ ] 既存の `{Country}{Category}Data` インターフェースに追加

#### 2.2 チャートコンポーネント作成
- [ ] **ファイル**: `frontend/src/components/country/{country}/{category}/{PascalCase}Chart.tsx`
- [ ] テンプレート: [templates/chart.tsx.md](templates/chart.tsx.md) を参照
- [ ] 必須実装:
  - [ ] 最新値表示（`SimpleLatestValueBox`）
  - [ ] 次回発表日表示（`nextRelease` prop）
  - [ ] **FMPマッピングがある場合のみ**:
    - [ ] タブ切替（時系列 / マーケットインパクト）
    - [ ] マーケットインパクトタブ（`MarketImpactTab`）
  - [ ] **FMPマッピングがない場合**:
    - [ ] マーケットインパクトタブは追加しない（発表履歴を取得できないため）
    - [ ] タブ不要の場合はシンプルな構造で実装
  - [ ] データ比較ボタン
  - [ ] 期間選択（`PeriodSelector`）
  - [ ] グラフ（`StandardLineChart` / `StandardBarChart`）

#### 2.3 カテゴリチャート統合
- [ ] **ファイル**: `frontend/src/components/country/{country}/{Country}{Category}Charts.tsx`
- [ ] import文追加
- [ ] コンポーネント追加
- [ ] data props渡す

#### 2.4 個別APIエンドポイント追加（ダッシュボードとは別に個別取得可能にする場合）
- [ ] **ファイル**: `backend/routers/{country}/{service_name}.py`
- [ ] 個別エンドポイント（例: `/api/{country}/{service}/balance-sheet`）を追加
- [ ] これにより `/compare?s=xxx` で直接データ取得可能になる

#### 2.5 ナビゲーション追加
- [ ] **ファイル**: `frontend/src/constants/countryData.tsx`
- [ ] 該当国・カテゴリの `subcategories` 配列に追加
- [ ] `code` はチャートの `<div id="...">` と一致させる
- [ ] 例: `{ code: 'sp-pmi', name: 'S&P Global PMI' }`

#### 2.6 データ比較機能追加（add_to_overlay: true の場合）
- [ ] **ファイル**: `frontend/src/constants/overlayConfig.ts`
- [ ] `OVERLAY_INDICATORS` 配列に追加
- [ ] テンプレート: [templates/overlay.md](templates/overlay.md) を参照
- [ ] **重要**: `apiEndpoint` は個別APIエンドポイントを指定する
  - 例: `/api/switzerland/snb/balance-sheet`（ダッシュボードAPIではなく個別API）
  - 個別APIがない場合は先に 2.4 で作成する

---

### Phase 3: 検証

#### 3.1 バックエンド検証
- [ ] APIエンドポイント動作確認
  ```bash
  curl http://localhost:8000/api/{country}/{category}/dashboard
  ```
- [ ] データが正しく取得されているか
- [ ] `next_release` が設定されているか
- [ ] キャッシュが動作しているか

#### 3.2 ダッシュボードキャッシュ無効化
- [ ] キャッシュクリア実行
  ```bash
  curl -X DELETE http://localhost:8000/api/{country}/{category}/dashboard/cache
  ```

#### 3.3 フロントエンド検証
- [ ] TypeScriptエラーなし
  ```bash
  cd frontend && npx tsc --noEmit
  ```
- [ ] ダッシュボードに表示されるか
- [ ] グラフが正常に描画されるか
- [ ] 最新値が表示されるか
- [ ] 次回発表日が表示されるか
- [ ] マーケットインパクトタブが機能するか
- [ ] データ比較ボタンが機能するか（遷移時にエラーなし）

---

## よくある実装漏れ

1. **画面表示されない**
   - ダッシュボードローダーに追加忘れ
   - カテゴリチャートにコンポーネント追加忘れ
   - 型定義追加忘れ
   - **ナビゲーション追加忘れ**: `countryData.tsx` の該当カテゴリに `subcategories` 追加が必要
   - **バックエンドサーバーの再起動が必要**
     - 新しいサービスやローダーを追加した場合、ファイルを保存しただけではホットリロードされないことがある
     - `uvicorn`を停止して再起動: `Ctrl+C` → `uvicorn main:app --reload`
   - **ダッシュボードキャッシュに古いデータが残っている**
     - キャッシュをクリアしないと新しいキーが含まれない
     - キャッシュクリア: `curl -X DELETE http://localhost:8000/api/{country}/{category}/dashboard/cache`
   - **フロントエンドのビルドキャッシュ**
     - ブラウザの開発者ツールで「キャッシュを無効化」を有効にする（Network → Disable cache）
     - または強制リロード: `Ctrl+Shift+R`

2. **マーケットインパクトが表示されない / 「発表履歴がありません」エラー**
   - `MarketImpactTab` の `indicatorId` が間違っている
   - `indicatorId` は `econalpha_id` と一致させる（FMPマッピング必須）
   - **FMPマッピングがない指標にはマーケットインパクトタブを追加しない**
     - FMPイベントがない外部データソース（SNB Data Portal等）の場合
     - マーケットインパクトAPIは `econalpha_id` でFMPから発表履歴を取得するため

3. **データ比較機能でエラー / データが取得できない**
   - `overlayConfig.ts` に追加忘れ
   - **`apiEndpoint` は個別APIエンドポイントを指定する**
     - 例: `/api/switzerland/snb/balance-sheet`（個別API）
     - **NG**: `/api/switzerland/policy`（ダッシュボードAPI - 自動で `/dashboard` が付与されてエラー）
   - 個別APIエンドポイントが存在しない場合は先に作成する
   - `dataKey` が実際のAPIレスポンスのキーと一致していない

4. **次回発表日が表示されない**
   - サービスで `get_next_release_by_pattern()` を呼んでいない
   - FMPマッピングが登録されていない
   - FMPにイベントがない場合は独自実装が必要（RSSフィード解析等）

5. **PDFからのデータ抽出が失敗する**
   - **PDFに時系列データがない場合**: 多くの政府/中央銀行PDFは当月データのみ記載。複数月のPDFを取得して時系列を構築する必要がある
   - **PDFエンコーディング問題**: 数字の千区切り（`'`や`,`）が特殊文字（Unicode Private Use Area等）に変換されることがある
     - 解決策: `re.sub(r'[^\d]', '', value_str)` で数字以外を全て除去
   - **テーブル認識失敗**: pdfplumberの`extract_tables()`が認識できないレイアウトがある
     - 解決策: `extract_text()`でテキスト全体を取得し、正規表現で抽出
   - **実装例**: `backend/services/switzerland/ch_job_vacancies_service.py`を参照
     - 複数PDFから各月データを抽出するパターン
     - PDF URLから年月を抽出するフォールバック

6. **レイアウトが他の指標と異なる / 見た目が統一されていない**
   - **ビューモード切り替えには必ず `ViewModeButtonGroup` を使用する**
     - NG: `Radio.Group` を使用してはいけない
     - OK: `ViewModeButtonGroup` コンポーネント（`usa/common/ChartComponents.tsx`）
   - **グラフ種別の使い分け**:
     - **原数値・前年比**: `StandardLineChart`（線グラフ）を使用
     - **前月比**: `StandardBarChart`（棒グラフ）を使用
     - 前年比は `showZeroLine={true}` を設定
   - **標準レイアウトパターン**:
     1. `SimpleLatestValueBox` - 最新値表示
     2. `ViewModeButtonGroup` - ビューモード切替（複数系列/前年比等の場合）
     3. `PeriodSelector` + `データ比較ボタン` - 横並びで配置
     4. グラフ（原数値/前年比は線グラフ、前月比は棒グラフ）
   - **参考実装**:
     - 単一系列: `frontend/src/components/country/switzerland/consumer/KofBarometerChart.tsx`
     - 複数系列切替: `frontend/src/components/country/switzerland/housing/CHMortgageRatesChart.tsx`
     - 前年比/前月比切替: `frontend/src/components/country/switzerland/housing/CHMortgageBalanceChart.tsx`

7. **Excelからのデータ抽出が失敗する / 「データが利用できません」エラー**
   - **Excelファイルの構造を必ず事前確認する**
     - 同じデータソース（例: SECO）でも、ファイルによって構造が異なる場合がある
     - 例: `qna_p_cssa.xlsx`（GDP生産アプローチ）と`qna_e_csa.xlsx`（GDP支出アプローチ）は構造が異なる
   - **ヘッダー行の位置を確認する**
     - Row 0にヘッダーがあるとは限らない（Row 10にヘッダーがある場合も）
     - 実際にExcelを読み込んで構造を確認するスクリプトを実行する
   - **検証方法**:
     ```python
     import requests, pandas as pd, io
     resp = requests.get(url, timeout=60)
     df = pd.read_excel(io.BytesIO(resp.content), sheet_name='sheet_name', header=None)
     # 各行・列の内容を出力して構造を把握
     for row in range(min(15, df.shape[0])):
         for col in range(min(20, df.shape[1])):
             val = df.iloc[row, col]
             if pd.notna(val):
                 print(f'Row {row}, Col {col}: {val}')
     ```
   - **列名検索時の注意**:
     - 検索対象の行を正確に指定する（例: `df.iloc[10, col]`でRow 10を検索）
     - 既存の類似サービスをコピーする際は、Excel構造の違いに注意
   - **実装例**: `backend/services/switzerland/ch_households_and_npish_service.py`を参照
     - SECO支出アプローチExcelの構造（Row 10がヘッダー行）

8. **データ比較ボタンで遷移しても指標が選択されない / データが表示されない**
   - **URLパラメータ形式が間違っている**
     - **NG**: `/compare?s=indicator1,indicator2`（カンマ区切りは認識されない）
     - **OK**: `/compare?s=indicator1&s=indicator2`（複数のsパラメータとして渡す）
   - `useCompareState.ts`は`searchParams.getAll('s')`で複数のsパラメータを取得するため、カンマ区切りだと単一の文字列として解釈される
   - **正しい実装例**:
     ```tsx
     // 単一指標
     onClick={() => window.open('/compare?s=ch_unemployment_rate', '_blank')}

     // 複数指標（正しい形式）
     onClick={() => window.open('/compare?s=ch_mortgage_rates_variable&s=ch_mortgage_rates_fixed', '_blank')}

     // 複数指標（間違った形式 - 動作しない）
     onClick={() => window.open('/compare?s=ch_mortgage_rates_variable,ch_mortgage_rates_fixed', '_blank')}
     ```

9. **SNB Data PortalのCSVパースでデータが取得できない / 1件しか取得できない**
   - **CSVの改行コードに`\r`（キャリッジリターン）が含まれている**
     - `strip('"')` だけでは `\r` が残り、`float()` 変換に失敗する
     - **解決策**: `strip().strip('"')` で空白文字と引用符の両方を除去
   - **正しい実装例**:
     ```python
     # 間違った実装（\rが残る）
     date_str = parts[0].strip('"')
     value_str = parts[6].strip('"')

     # 正しい実装
     date_str = parts[0].strip().strip('"')
     value_str = parts[6].strip().strip('"')
     ```
   - **実装例**: `backend/services/switzerland/ch_mortgage_balance_service.py`を参照

10. **テーブル表示を追加したら他指標とレイアウトが不統一になった**
    - **基本的にテーブル表示は使用しない**
      - 入力フォームで`show_table: true`が指定されても、他指標との統一性を優先
      - テーブルが必要な特別な理由（カテゴリ別内訳表示等）がない限り追加しない
    - **標準レイアウト（テーブルなし）**:
      1. `SimpleLatestValueBox` - 最新値表示
      2. `ViewModeButtonGroup` - ビューモード切替（複数系列/前年比等の場合）
      3. `PeriodSelector` + `データ比較ボタン` - 横並び
      4. `StandardLineChart` / `StandardBarChart` - グラフ
    - **テーブルを追加すべきケース**:
      - カテゴリ別内訳を表示する必要がある（例: CPIカテゴリ別）
      - 予測データと実績データを比較表示する（例: 機械受注見通し）

11. **Statistics Canadaのデータ型確認ミス（INDEX vs パーセンテージ）**
    - **重要: APIが返すデータの「型」を必ず確認する**
      - Table 18-10-0004-01: CPIの**インデックス値**（2002=100基準）を返す
      - Table 18-10-0006-01: 前月比（MoM）を返す
      - **インデックス値を前年比として直接使用すると165%のような異常値になる**
    - **前年比の計算方法**（インデックスから算出）:
      ```python
      # インデックスから前年比を計算
      def _fetch_cpi_yoy(self) -> Dict[str, float]:
          # 先にインデックスデータをindex_mapに格納
          index_map: Dict[str, float] = {}  # {"2024-01-01": 165.2, ...}

          # 前年比（YoY）を計算
          result = {}
          for date_str, current_index in index_map.items():
              dt = datetime.strptime(date_str, "%Y-%m-%d")
              prev_year_date = f"{dt.year - 1:04d}-{dt.month:02d}-01"
              if prev_year_date in index_map:
                  prev_index = index_map[prev_year_date]
                  if prev_index > 0:
                      yoy = ((current_index - prev_index) / prev_index) * 100
                      result[date_str] = round(yoy, 2)
          return result
      ```
    - **検証方法**: Statistics Canada WebサイトまたはWebFetchで実際のデータ型を確認
      - 数値が100前後 → インデックス値（変換が必要）
      - 数値が-5〜+10程度 → 前年比/前月比（そのまま使用可能）

12. **Statistics Canada CSVの列名フィルタリング失敗（部分一致が必要）**
    - **CSVの列値は長い説明文形式になっている**
      - **NG**: `df[df['Alternative measures'] == 'CPI-trim']`（完全一致では見つからない）
      - **OK**: `df[df['Alternative measures'].str.contains('CPI-trim', na=False)]`（部分一致）
    - **実際の列値の例**:
      ```
      # 期待値（間違い）
      'CPI-trim'

      # 実際の値（正しい）
      'Measure of core inflation based on a trimmed mean approach, CPI-trim (year-over-year percent change)'
      ```
    - **正しい実装例**:
      ```python
      core_indicators = {
          'CPI-trim (year-over-year': 'trim',
          'CPI-median (year-over-year': 'median',
          'CPI-common (year-over-year': 'common',
      }

      for search_pattern, key in core_indicators.items():
          indicator_data = df[
              (df['Alternative measures'].str.contains(search_pattern, na=False)) &
              (df['GEO'] == 'Canada')
          ].copy()
      ```
    - **検証方法**: CSVをダウンロードしてPythonで列値を出力して確認
      ```python
      import pandas as pd
      df = pd.read_csv('path/to/data.csv')
      print(df['Column Name'].unique())  # 実際の列値を確認
      ```

13. **新規国のAPIエンドポイントをuseOverlayData.tsに追加忘れ**
    - **データ比較ページで「データの読み込みに失敗しました」エラーが発生する**
    - **原因**: `useOverlayData.ts`の`directApiPatterns`に新規国のAPIパターンが登録されていない
      - 登録がない場合、`/dashboard`が自動付与されて404エラーになる
      - 例: `/api/canada/statcan/cpi` → `/api/canada/statcan/cpi/dashboard`（存在しない）
    - **解決策**: `directApiPatterns`に新規国のAPIパターンを追加
      ```typescript
      const directApiPatterns = [
          // 既存パターン
          '/api/switzerland/',
          // 新規国を追加
          '/api/canada/boc/',
          '/api/canada/statcan/',
      ];
      ```
    - **新規国を追加する際のチェックリスト**:
      1. 個別APIエンドポイントを作成（例: `/api/canada/statcan/cpi`）
      2. `overlayConfig.ts`に指標を追加
      3. **`useOverlayData.ts`の`directApiPatterns`に国のAPIパターンを追加** ← 忘れやすい
    - **実装例**: `frontend/src/hooks/useOverlayData.ts`を参照

14. **複数系列をマージする際のNone値エラー**
    - **問題**: 複数系列（例: TOTAL/BOC/AP）を日付でマージする際、一部系列にデータがない日があるとNoneが発生
    - **エラー例**: `TypeError: unsupported format string passed to NoneType.__format__`
    - **原因**: `latest['total']:,.0f` のようなフォーマット指定でNoneを渡した場合
    - **解決策1**: メイン系列がNoneのレコードを除外
      ```python
      # totalがNoneのレコードを除外
      result = [item for item in result if item.get("total") is not None]
      ```
    - **解決策2**: ログ出力時にNoneチェック
      ```python
      if result and latest.get('total') is not None:
          print(f"Latest: {latest['total']:,.0f}")
      ```
    - **実装例**: `backend/services/canada/ca_government_deposits_service.py`を参照

15. **Statistics Canada ZIP/CSVのデータ構造確認ミス**
    - **重要: 実装前に必ずCSVのデータ構造を確認する**
      - Statistics CanadaのテーブルはZIPファイルでCSVを提供
      - **テーブルによって列構成が全く異なる**
      - 入力フォームで指定されたフィルタリング条件（Type of unit等）が存在しない場合がある
    - **よくあるエラーパターン**:
      ```python
      # 間違い: 存在しない列でフィルタリング → 空の結果
      canada_df = df[
          (df['GEO'] == 'Canada') &
          (df['Type of unit'] == 'Total units') &  # ← この列が存在しない場合がある
          (df['Housing estimates'] == 'Housing starts')
      ]
      ```
    - **正しいアプローチ**:
      1. まずCSVの実際の列構成を確認
      2. 必要な列のみでフィルタリング
      ```python
      # 事前確認スクリプト
      import requests, zipfile, io, pandas as pd
      url = 'https://www150.statcan.gc.ca/n1/tbl/csv/34100158-eng.zip'
      resp = requests.get(url, timeout=90)
      z = zipfile.ZipFile(io.BytesIO(resp.content))
      csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]
      with z.open(csv_name) as f:
          df = pd.read_csv(f, low_memory=False)
      print(f'Columns: {df.columns.tolist()}')
      print(f'GEO unique: {df["GEO"].unique()[:5]}')
      # 各列のユニーク値を確認してからフィルタリング条件を決定
      ```
    - **実装例**: `backend/services/canada/ca_housing_starts_service.py`を参照

16. **単位の選択ミス（億・百万・十億等）**
    - **重要: 入力フォームで指定された単位を必ず使用する**
      - ユーザーが`unit: "億CHF"`と指定した場合は億CHF単位を使用
      - 勝手に単位を変更しない（百万→十億等の変換をしない）
    - **APIから取得した原数値の桁数を確認して変換係数を決定**:
      - 億単位: `value = value_raw / 100_000_000`
      - 十億単位: `value = value_raw / 1_000_000_000`
      - 百万単位: `value = value_raw / 1_000_000`
    - **確認方法**: APIレスポンスまたはキャッシュファイルで実際の`value`を確認
      ```bash
      # キャッシュファイルで確認
      cat backend/data/cache/{country}/{category}/{indicator}_cache.json | jq '.latest.value_chf'
      ```
    - **単位変換の実装箇所（4箇所すべて統一する）**:
      1. バックエンドサービス: `value = value_raw / 100_000_000`（億）
      2. バックエンドmetadata: `"unit": "100 million CHF"`（億CHF）
      3. フロントエンドチャート: `unit={viewMode === 'value' ? '億CHF' : undefined}`
      4. overlayConfig: `unit: '億CHF'`
    - **Y軸フォーマッタも調整する**:
      - 億単位: `yAxisFormatter={(v) => \`${v.toFixed(1)}\`}` と `yDomain={['dataMin - 0.5', 'dataMax + 0.5']}`
      - billion単位: `yAxisFormatter={(v) => \`${v.toFixed(2)}\`}` と `yDomain={['dataMin - 0.05', 'dataMax + 0.05']}`
      - million単位: `yAxisFormatter={(v) => \`${(v / 1000).toFixed(0)}K\`}` と `yDomain={['dataMin - 10000', 'dataMax + 10000']}`
    - **実装例**: `backend/services/switzerland/ch_mortgage_balance_service.py`を参照

17. **next_releaseの型定義ミス（string vs object）**
    - **問題**: フロントエンドで`next_release?: string`と定義したが、APIが返すのはオブジェクト
    - **症状**: チャートコンポーネントでクラッシュ、「データが利用できません」表示
    - **原因**: FMPから取得される`next_release`は以下の形式のオブジェクト:
      ```json
      {
        "date": "2026-02-16",
        "datetime_jst": "2026-02-16T22:15:00+09:00",
        "time_jst": "22:15",
        "label": "Housing Starts (Jan)",
        "estimate": null
      }
      ```
    - **正しい型定義**:
      ```typescript
      export interface CaHousingStartsNextRelease {
        date: string           // YYYY-MM-DD形式
        datetime_jst: string   // ISO8601形式（JST）
        time_jst: string       // HH:MM形式
        datetime_toronto: string // ISO8601形式（トロント時間）
        time_toronto: string   // HH:MM形式
        label: string          // 例: "Housing Starts (Jan)"
        estimate: number | null
      }

      export interface CaHousingStartsData {
        data: CaHousingStartsItem[]
        latest: CaHousingStartsItem | null
        metadata: Record<string, unknown>
        next_release?: CaHousingStartsNextRelease | null  // string ではなくオブジェクト
      }
      ```
    - **チャートコンポーネントでの渡し方**:
      ```tsx
      // 間違い: stringをオブジェクトでラップ
      nextRelease={data.next_release ? { date: data.next_release } : null}

      // 正しい: そのまま渡す（すでにオブジェクト）
      nextRelease={data.next_release ?? null}
      ```
    - **検証方法**: APIレスポンスで`next_release`の形式を確認
      ```bash
      curl http://localhost:8000/api/canada/statcan/housing-starts | jq '.next_release'
      ```

18. **ダッシュボードキャッシュクリア後のタイムアウト問題（修正済み）**
    - **問題**: ダッシュボードキャッシュクリア後、全サービスが`force_refresh=True`で外部API呼び出しを行いタイムアウトしていた
    - **原因**: `_detect_stale_indicators(None)` が `{"all"}` を返す設計だったため、キャッシュミス時に全サービスが強制リフレッシュ対象になっていた
    - **修正内容**: 全33ローダーの `_detect_stale_indicators` で `if last_updated is None: return {"all"}` を `return stale`（空セット）に変更済み
    - **現在の動作**: キャッシュクリア後も各サービスは自身のRedisキャッシュを使って `force_refresh=False` で高速にデータを返す（78秒→0.04秒に改善）
    - **注意**: この修正により、ダッシュボードキャッシュクリアは安全に実行可能。個別サービスのRedisキャッシュは別管理

19. **Statistics Canada大規模テーブル（数千万行）の取得問題**
    - **問題**: 一部のStatistics Canadaテーブル（例: Table 34-10-0292-01 Building Permits）は3,500万行以上あり、全件CSVダウンロードは非現実的
    - **症状**: ダウンロードに数分〜タイムアウト、メモリ不足、pandas読み込み失敗
    - **解決策**: WDS API + vectorId を使用（必要な系列のみ取得）
    - **WDS実装手順**:
      1. **cube metadataでdimension構造を確認**:
         ```python
         import requests
         BASE = 'https://www150.statcan.gc.ca/t1/wds/rest'
         resp = requests.post(f'{BASE}/getCubeMetadata', json=[{'productId': 34100292}], timeout=60)
         meta = resp.json()[0]['object']
         # dimension構造とmemberIdを確認
         ```
      2. **coordinateからvectorIdを取得**（1回だけ）:
         ```python
         # coordinate = 各dimensionのmemberIdを「.」で連結
         # 例: Canada(1).Total(1).Total(1).Value(1).SA(2) = '1.1.1.1.2'
         resp = requests.post(f'{BASE}/getSeriesInfoFromCubePidCoord',
                             json=[{'productId': 34100292, 'coordinate': '1.1.1.1.2'}], timeout=30)
         vector_id = resp.json()[0]['object']['vectorId']
         ```
      3. **vectorIdでデータ取得**（毎回）:
         ```python
         resp = requests.post(f'{BASE}/getDataFromVectorsAndLatestNPeriods',
                             json=[{'vectorId': vector_id, 'latestN': 100}], timeout=30)
         data_points = resp.json()[0]['object']['vectorDataPoint']
         ```
    - **WDS注意事項**:
      - 更新時刻: 毎営業日 8:30am Eastern
      - 更新中は409エラーが発生することがある → 指数バックオフ＋リトライ
      - レート制限: IPあたり50rps
    - **代替方法**: cube metadata CSV（約50KB）をダウンロードしてvectorIdを抽出
    - **実装例**: `backend/services/canada/ca_building_permits_service.py`（WDS実装予定）

---

## 参考ファイル

実装時は以下の既存ファイルを参考にしてください：

- サービス: `backend/services/switzerland/ch_unemployment_rate_service.py`
- ローダー: `backend/services/dashboard/loaders/switzerland_employment.py`
- チャート: `frontend/src/components/country/switzerland/consumer/KofBarometerChart.tsx`
- 型定義: `frontend/src/hooks/useDashboardData.ts`
- オーバーレイ: `frontend/src/constants/overlayConfig.ts`
