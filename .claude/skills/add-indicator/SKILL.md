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

# ===== ヒートマップ表示 =====
# 前月比/前期比がある指標で、複数系列（総合/コア等）がある場合に使用
# 上段: [前月比/前期比 | 前年比] 下段: [チャート | ヒートマップ]
show_heatmap: false           # ヒートマップ表示するか（前月比/前期比+複数系列の場合にtrue）
heatmap_type: none            # ヒートマップ種別: none, monthly, quarterly
heatmap_data_types:           # ヒートマップ切替項目（例: 総合/コア/コアコア）
  - total: '総合'
  - core: 'コア'

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

> ### ⚠️ 厳守: マーケットサービスのスケジューラー登録
> **`backend/services/market/` に新しいサービスを追加した場合、必ず `backend/services/market/market_scheduler.py` にスケジュールジョブを登録すること。**
> 登録漏れがあるとデータが自動更新されず、ユーザーがアクセスしない限り古いデータのままになる。
>
> **必須手順:**
> 1. サービスのdocstringに `更新スケジュール:` を記載（例: `更新スケジュール: 日次（JST 8:30）`）
> 2. `market_scheduler.py` の該当時間帯のジョブに `_import_service()` + `_safe_call()` を追加
> 3. `market_scheduler.py` 冒頭のスケジュール一覧コメントを更新
>
> **スケジュール時間帯の目安:**
> - JST 5:00: 気象データ (NOAA)
> - JST 7:00: 朝の日次更新 (GEX/DIX, 日経YoY, 電子部品等)
> - JST 8:00: CBOE PCR
> - JST 8:30: 貴金属・銅 (Gold/Silver/Copper ETF & Stocks)
> - JST 9:00: Fear & Greed, NAAIM(金曜)
> - JST 15:30-16:00: 東証引け後 (騰落レシオ, JPX投資部門別, 日経ダブルインバース)
> - JST 20:30: JPX PCR
> - 土曜 9:00-10:00: 週次エネルギー (EIA, リグカウント, 天然ガス等)
> - 毎月10日: TSMC Revenue

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
  - [ ] docstringに `更新スケジュール:` を記載

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

#### 1.5 スケジューラー登録（マーケットサービスの場合）
- [ ] **ファイル**: `backend/services/market/market_scheduler.py`
- [ ] 該当時間帯のジョブメソッドに追加、または新しいジョブを作成
- [ ] `_import_service("xxx_service", "xxx_service")` + `_safe_call()` でラップ
- [ ] 冒頭のスケジュール一覧コメントを更新
- [ ] **⚠️ この手順を飛ばすとデータが自動更新されない**

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

0. **マーケットサービスのデータが自動更新されない**
   - `market_scheduler.py` にスケジュールジョブが登録されていない
   - サービスのdocstringに `更新スケジュール:` が記載されていない
   - **必ず Phase 1.5 のステップを実行すること**

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

   > ### ⚠️ 厳守: チャートレイアウト標準（Pattern B）
   > **全指標で以下の順序・配置を必ず守ること。例外は認めない。**
   >
   > **【ビューモードあり + 比較ボタンあり（標準）】**
   > ```
   > 1. LatestValueBox / SimpleLatestValueBox   ← 最新値（最上段）
   > 2. [ViewModeButtonGroup]  [データ比較ボタン]  ← 同一行・左右に配置
   > 3. PeriodSelector                           ← 単独行
   > 4. グラフ
   > ```
   >
   > **【ビューモードなし + 比較ボタンあり】**
   > ```
   > 1. SimpleLatestValueBox   ← 最新値
   > 2.           [データ比較ボタン]  ← 右端に単独配置（justifyContent: flex-end）
   > 3. PeriodSelector         ← 単独行
   > 4. グラフ
   > ```
   >
   > **絶対NG（やってはいけない配置）**:
   > - `PeriodSelector` と `データ比較ボタン` を同一行に配置する → **禁止**
   > - `ViewModeButtonGroup` を単独行に配置して `データ比較ボタン` を別行（PeriodSelector行）にする → **禁止**
   > - `ViewModeButtonGroup` → 改行 → `PeriodSelector + 比較ボタン` の順序 → **禁止**
   >
   > **NG例（最もよくある間違いパターン）**:
   > ```tsx
   > // ❌ 禁止パターン
   > <ViewModeButtonGroup ... />           {/* 単独行 */}
   > <div style={{ display: 'flex', justifyContent: 'space-between' }}>
   >   <PeriodSelector ... />
   >   <Button>データ比較</Button>         {/* PeriodSelectorと同行 → 禁止 */}
   > </div>
   > ```
   >
   > **OK例（正しいパターン）**:
   > ```tsx
   > // ✅ 正しいパターン
   > <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
   >   <ViewModeButtonGroup ... />
   >   <Button>データ比較</Button>         {/* ViewModeButtonGroupと同行 ✅ */}
   > </div>
   > <PeriodSelector ... />               {/* 単独行 ✅ */}
   > ```

   - **ビューモード切り替えには必ず `ViewModeButtonGroup` を使用する**
     - NG: `Radio.Group` を使用してはいけない
     - OK: `ViewModeButtonGroup` コンポーネント（`usa/common/ChartComponents.tsx`）
   - **グラフ種別の使い分け**:
     - **原数値・前年比**: `StandardLineChart`（線グラフ）を使用
     - **前月比/前期比**: `StandardBarChart`（棒グラフ）を使用
     - 前年比は `showZeroLine={true}` を設定
   - **標準レイアウト実装例（Pattern B）**:
     ```tsx
     {/* 1. 最新値表示 */}
     <SimpleLatestValueBox ... />

     {/* 2. ViewModeButtonGroup + データ比較ボタン ← 必ず同一行 */}
     <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
       <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
       <Tooltip title="比較ページを開く">
         <Button icon={<AreaChartOutlined />}
           onClick={() => window.open('/compare?s=indicator_id', '_blank')}>
           データ比較
         </Button>
       </Tooltip>
     </div>

     {/* 3. PeriodSelector ← 単独行（比較ボタンと同一行にしてはいけない） */}
     <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

     {/* 4. グラフ */}
     {viewMode === 'raw' && <StandardLineChart ... />}
     {viewMode === 'yoy' && <StandardLineChart showZeroLine={true} ... />}
     {viewMode === 'mom' && <StandardBarChart ... />}
     ```
   - **★推奨: 前月比/前期比＋前年比の標準レイアウト（複数系列がある場合）**:
     ```
     上段: [前期比/前月比 | 前年比]  [データ比較]  ← ViewModeButtonGroup（同一行）
     下段: [チャート | ヒートマップ]               ← 前期比/前月比のときのみ表示

     前年比 → 折れ線グラフ（全系列同時表示、凡例クリック切替）
     前月比/前期比チャート → DataTypeButtonGroup（総合/コア/その他）+ 棒グラフ
     前月比/前期比ヒートマップ → テーブル内で総合/コア/その他切替
     ```
     - 指標によって `前月比`（monthly）か `前期比`（quarterly）かが異なる
     - 総合/コア以外の項目がある場合は `DataTypeButtonGroup` の選択肢を追加
     - テンプレート: [templates/chart.tsx.md](templates/chart.tsx.md) の「チャート＋ヒートマップパターン★推奨」を参照
   - **参考実装（Pattern B 準拠）**:
     - 単一系列: `frontend/src/components/country/switzerland/consumer/KofBarometerChart.tsx`
     - 複数系列切替: `frontend/src/components/country/switzerland/housing/CHMortgageRatesChart.tsx`
     - ★前期比/前年比+ヒートマップ（四半期）: `frontend/src/components/country/newzealand/consumer/NzRetailSalesChart.tsx`
     - ★前月比/前年比+ヒートマップ（月次）: `frontend/src/components/country/japan/price/NationalCPIChart.tsx`
     - ★前期比/前年比+ヒートマップ（四半期・多系列）: `frontend/src/components/country/australia/inflation/AuQuarterlyCpiChart.tsx`
     - ★ビューモード付き多系列: `frontend/src/components/country/china/policy/CnAggregateFinancingChart.tsx`

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

20. **前月比棒グラフのDataType切替ボタンに手動Buttonループを使ってはいけない**
    - **問題**: 手動で`Button`をmapしてDataType切替を実装すると、他の指標チャートとレイアウト・スタイルが不統一になる
    - **NG**:
      ```tsx
      // ❌ 禁止: 手動Buttonループ
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
        {CPI_DATA_TYPE_OPTIONS.map(opt => (
          <Button key={opt.type} type={dataType === opt.type ? 'primary' : 'default'}
            size="small" onClick={() => setDataType(opt.type)} style={{ marginRight: 4 }}>
            {opt.label}
          </Button>
        ))}
      </div>
      ```
    - **OK**:
      ```tsx
      // ✅ 正しい: DataTypeButtonGroupコンポーネントを使用
      import { DataTypeButtonGroup } from '../../usa/common/ChartComponents'
      <DataTypeButtonGroup options={CPI_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
      ```
    - **配置順序（前月比チャートモード時）**:
      1. `DataTypeButtonGroup` — DataType切替（総合/コア等）
      2. `PeriodSelector` — 期間選択
      3. `StandardBarChart` — 棒グラフ
    - **参考実装**: `frontend/src/components/country/japan/price/NationalCPIChart.tsx`

21. **NBS（中国国家統計局）APIの時代分割コード体系**
    - **問題**: NBS統計データAPI（`data.stats.gov.cn/easyquery.htm`）は同一指標でも時代別にコードが分かれている
    - **時代区分**: 2016-2020 / 2021-2025 / 2026+ の3期間
    - **コード命名パターン**:
      - 2016-2020: `A01010101`（基本コード）
      - 2021-2025: `A01010G01`（Gプレフィックス）
      - 2026+: `A01010J01`（Jプレフィックス）
    - **一部の指標は2016-2020にコードが存在しない**:
      - 例: コアCPI（食品・エネルギー除く）は2021-2025以降のみ（`A01010G0D`）
      - 2016-2020のCSVにもコアCPI行がない → **データソースの制約であり、実装の問題ではない**
    - **食品CPI等はcross-periodコード（全時代共通）**:
      - 例: `A01010301`（食品CPI YoY）は2016〜2026+の全データを返す
    - **APIコード特定方法**:
      ```python
      # 特定時代の全サブカテゴリコードを一括取得
      import requests, json
      url = 'https://data.stats.gov.cn/easyquery.htm'
      params = {
          'm': 'QueryData', 'dbcode': 'hgyd', 'rowcode': 'zb', 'colcode': 'sj',
          'wds': json.dumps([]),
          'dfwds': json.dumps([
              {'wdcode':'sj','valuecode':'202512'},  # 対象月
              {'wdcode':'zb','valuecode':'A01010G'}   # 親コード（2021-2025 YoY）
          ]),
          'k1': '1'
      }
      resp = requests.get(url, params=params, timeout=30)
      # → 全子コード（G01〜G0D等）とその値が返る
      # CSVの行順序と値を照合してコードを特定する
      ```
    - **NBS APIの値はインデックス（base=100）**: `percent = value - 100`
      - 例: 100.8 → +0.8%, 99.3 → -0.7%
    - **実装パターン**: 各系列の全時代コードをリストで保持し、マージ（後の時代が優先）
      ```python
      NBS_API_CODES = {
          "cpi_yoy": ["A01010101", "A01010G01", "A01010J01"],  # 3時代
          "core_yoy": ["A01010G0D", "A01010J0D"],              # 2時代のみ
          "food_yoy": ["A01010301"],                           # cross-period
      }
      ```
    - **実装例**: `backend/services/china/cn_cpi_service.py`

22. **変動幅が大きい系列は右Y軸に分離する**
    - **問題**: 食品CPIのように変動幅が大きい系列（-20%〜+30%）と、CPI総合のように変動幅が小さい系列（-1%〜+3%）を同じY軸で表示すると、小変動の系列が平坦に見える
    - **解決策**: `StandardLineChart`の`yAxisId: 'right'`を使って右Y軸に分離
      ```tsx
      <StandardLineChart
        data={filteredData}
        lines={[
          { dataKey: 'yoy', color: COLOR_TOTAL, name: 'CPI総合(L)' },
          { dataKey: 'core_yoy', color: COLOR_CORE, name: 'コアCPI(L)' },
          { dataKey: 'food_yoy', color: COLOR_FOOD, name: '食品CPI(R)', yAxisId: 'right' },
        ]}
        yAxisFormatter={(v) => `${v.toFixed(1)}%`}
        rightYAxisFormatter={(v) => `${v.toFixed(0)}%`}
        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
      />
      ```
    - **凡例のL/R表記**: 右Y軸の系列は名前に`(R)`、左Y軸は`(L)`を付ける
    - **適用すべきケース**:
      - 食品CPI vs CPI総合/コア/非食品
      - 原数値（水準）と前年比（%）を同時表示する場合
    - **実装例**: `frontend/src/components/country/china/inflation/CnCpiChart.tsx`

23. **EIA エネルギー在庫チャート（原油価格オーバーレイ付き）の実装パターン**

    EIA週次在庫チャート（原油在庫、クッシング在庫、蒸留燃料在庫、ガソリン在庫等）は、通常の国別経済指標とは異なる **市場カテゴリ専用パターン（Pattern E: Energy）** を使用する。

    > ### ⚠️ 厳守: EIAエネルギーチャートレイアウト（Pattern E）
    > **以下のパターンを必ず守ること。Pattern B（標準レイアウト）とは異なる。**
    >
    > **共通構造:**
    > ```
    > 1. LatestValueBox（LATEST_VALUE_BOX_STYLE）← 最新値 + 次回発表日（データ比較ボタンはここに置かない）
    > 2. <Tabs>（antd Tabs）← 「時系列」と「マーケットインパクト」の2タブ
    >    └─ 時系列タブ:
    >       ├─ [ViewModeButtonGroup 水準/前月比/前年比]  [データ比較ボタン]  ← 同一行
    >       ├─ [ViewModeButtonGroup チャート/ヒートマップ]  ← viewMode === 'mom' の時のみ表示（単独行）
    >       ├─ viewMode別の条件付きレンダリング:
    >       │   ├─ raw:  PeriodSelector + ComposedChart（水準 + WTI原油オーバーレイ）
    >       │   ├─ yoy:  PeriodSelector + ComposedChart（YoY% + WTI原油オーバーレイ + ReferenceLine y=0）
    >       │   ├─ mom + chart:  PeriodSelector + ComposedChart（Bar で MoM% + ReferenceLine y=0）
    >       │   └─ mom + heatmap:  MonthlyTable（前月比ヒートマップ）
    >    └─ マーケットインパクトタブ:
    >       └─ <MarketImpactTab indicatorId="..." />
    > ```

    #### 重要な相違点（Pattern B との違い）

    | 項目 | Pattern B（標準） | Pattern E（エネルギー） |
    |------|------------------|----------------------|
    | タブ切替 | なし or ViewModeButtonGroup | **antd `<Tabs>`** で「時系列/マーケットインパクト」を切替 |
    | ViewMode | `'value' \| 'yoy'` 等 | **`'raw' \| 'mom' \| 'yoy'`**（3モード: 水準/前月比/前年比） |
    | DisplayMode | なし | **`'chart' \| 'heatmap'`**（`viewMode === 'mom'` の時のみ表示） |
    | データ比較ボタン位置 | LatestValueBox外の同一行 | **タブ内部**（時系列タブの ViewModeButtonGroup と同一行） |
    | LatestValueBoxにデータ比較ボタン | あり | **なし** |
    | グラフコンポーネント | StandardLineChart / StandardBarChart | **ComposedChart**（Recharts直接使用） |
    | 原油価格Y軸 | なし | **右Y軸 + `reversed` prop**（水準・前年比モードのみ） |
    | チャートmargin | 指定なし | **`CHART_MARGIN`**（`chartConstants.ts` からimport） |
    | MoMデータ | バックエンド提供 | **フロントエンドで算出**（週次→月平均→MoM%） |
    | 前年比ヒートマップ | あることもある | **なし**（ヒートマップは前月比のみ） |

    #### State定義
    ```tsx
    type ViewMode = 'raw' | 'mom' | 'yoy'                  // ← 水準/前月比/前年比（3モード）
    const VIEW_MODE_OPTIONS = [
      { mode: 'raw' as ViewMode, label: '水準' },
      { mode: 'mom' as ViewMode, label: '前月比' },
      { mode: 'yoy' as ViewMode, label: '前年比' },
    ]

    type ActiveTab = 'timeseries' | 'market_impact'         // ← Tabs用
    type DisplayMode = 'chart' | 'heatmap'                   // ← チャート/ヒートマップ（前月比のみ）
    const DISPLAY_MODE_OPTIONS = [
      { mode: 'chart' as DisplayMode, label: 'チャート' },
      { mode: 'heatmap' as DisplayMode, label: 'ヒートマップ' },
    ]

    const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
    const [viewMode, setViewMode] = useState<ViewMode>('raw')
    const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
    ```

    #### 原油価格Y軸の反転方法

    - **NG（動作しない）**: `domain={['dataMax * 1.1', 'dataMin * 0.9']}`（domain値を逆にしても反転しない）
    - **OK（正しい方法）**: `<YAxis reversed ... />` propを使用
    ```tsx
    <YAxis
      yAxisId="oil"
      orientation="right"
      reversed                                          // ← これで反転
      domain={['dataMin * 0.9', 'dataMax * 1.1']}       // ← domainは通常通り
      tickFormatter={(v: number) => `$${v.toFixed(0)}`}
      stroke={COLOR_OIL}
      tick={{ fill: COLOR_OIL, fontSize: 10 }}
      width={50}
      axisLine={{ stroke: COLOR_OIL, strokeDasharray: '4 3' }}
    />
    ```

    #### 原油価格ラインのスタイル
    ```tsx
    <Line
      yAxisId="oil"
      type="monotone"
      dataKey="oil_price"
      name="WTI原油 (USD/bbl, 反転)"
      stroke={COLOR_OIL}          // '#ef4444' (Red)
      strokeWidth={1.5}
      strokeDasharray="4 3"       // 破線
      dot={false}
      hide={hiddenSeries.has('oil_price')}
      connectNulls
      isAnimationActive={false}   // ← 必須
    />
    ```

    #### 前月比（MoM）データ算出パターン（週次→月平均→MoM%）

    週次データはバックエンドからMoMが提供されないため、フロントエンドで算出する。

    **Step 1: 月平均の算出**
    ```tsx
    const monthAvg = useMemo(() => {
      if (!mergedData.length) return {} as Record<string, number>
      const monthAccum: Record<string, number[]> = {}
      for (const item of mergedData) {
        const d = new Date(item.date)
        const val = item.value  // ← メインの在庫データ系列
        if (val == null) continue
        const key = `${d.getFullYear()}-${String(d.getMonth()).padStart(2, '0')}`
        if (!monthAccum[key]) monthAccum[key] = []
        monthAccum[key].push(val)
      }
      const avg: Record<string, number> = {}
      for (const [key, vals] of Object.entries(monthAccum)) {
        avg[key] = vals.reduce((a, b) => a + b, 0) / vals.length
      }
      return avg
    }, [mergedData])
    ```

    **Step 2: MoMヒートマップデータ（直近10年分）**
    ```tsx
    const momHeatmapData = useMemo(() => {
      const currentYear = new Date().getFullYear()
      const startYear = currentYear - 9
      const years: number[] = []
      for (let y = startYear; y <= currentYear; y++) years.push(y)
      const monthlyData: Record<number, Record<number, number | null>> = {}
      for (const year of years) {
        monthlyData[year] = {}
        for (let m = 0; m < 12; m++) {
          const curVal = monthAvg[`${year}-${String(m).padStart(2, '0')}`]
          if (curVal == null) { monthlyData[year][m] = null; continue }
          let prevYear = year; let prevMonth = m - 1
          if (prevMonth < 0) { prevMonth = 11; prevYear-- }
          const prevVal = monthAvg[`${prevYear}-${String(prevMonth).padStart(2, '0')}`]
          monthlyData[year][m] = (prevVal != null && prevVal !== 0)
            ? Math.round(((curVal - prevVal) / prevVal) * 10000) / 100 : null
        }
      }
      return { years, monthlyData }
    }, [monthAvg])
    ```

    **Step 3: MoMバーチャートデータ**
    ```tsx
    const momChartData = useMemo(() => {
      const entries = Object.entries(monthAvg).sort(([a], [b]) => a.localeCompare(b))
      const result: { date: string; mom: number | null }[] = []
      for (let i = 1; i < entries.length; i++) {
        const [curKey, curVal] = entries[i]
        const [, prevVal] = entries[i - 1]
        const [y, m] = curKey.split('-').map(Number)
        result.push({
          date: `${y}-${String(m + 1).padStart(2, '0')}-15`,
          mom: (prevVal != null && prevVal !== 0)
            ? Math.round(((curVal - prevVal) / prevVal) * 10000) / 100 : null,
        })
      }
      return result
    }, [monthAvg])

    const filteredMomChartData = useMemo(() => {
      if (!momChartData.length) return []
      if (currentPeriod === 'all') return momChartData
      const years = typeof currentPeriod === 'number' ? currentPeriod : 5
      const cutoff = new Date()
      cutoff.setFullYear(cutoff.getFullYear() - years)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      return momChartData.filter(d => d.date >= cutoffStr)
    }, [momChartData, currentPeriod])
    ```

    #### 完全なレイアウト構造
    ```tsx
    <ChartContainer title="..." dataSource="EIA" sourceUrl="..." showPeriodSelector={false}>
      {/* 1. 最新値（データ比較ボタンはここに置かない） */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {/* 日付、在庫値、YoY、WTI原油価格、次回発表日 */}
        </div>
      </div>

      {/* 2. タブ切替（antd Tabs） */}
      <Tabs activeKey={activeTab} onChange={(key) => setActiveTab(key as ActiveTab)} style={{ marginTop: 8 }}
        items={[
          {
            key: 'timeseries', label: '時系列',
            children: (
              <>
                {/* 水準/前月比/前年比 + データ比較ボタン（同一行） */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode}
                    onChange={(m) => setViewMode(m as ViewMode)} />
                  <Tooltip title="比較ページを開く">
                    <Button icon={<AreaChartOutlined />}
                      onClick={() => window.open('/compare?s=indicator_id', '_blank')}>
                      データ比較
                    </Button>
                  </Tooltip>
                </div>

                {/* チャート/ヒートマップ切替（前月比のみ表示） */}
                {viewMode === 'mom' && (
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode}
                      onChange={(m) => setDisplayMode(m as DisplayMode)} />
                  </div>
                )}

                {/* 水準チャート */}
                {viewMode === 'raw' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                        {/* CartesianGrid, XAxis, YAxis(left), YAxis(oil, reversed), Tooltip, Legend */}
                        <Line yAxisId="left" dataKey="value" name="在庫名 (千bbl)" ... isAnimationActive={false} />
                        <Line yAxisId="oil" dataKey="oil_price" name="WTI原油 (USD/bbl, 反転)" ... isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* 前年比チャート */}
                {viewMode === 'yoy' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                        {/* CartesianGrid, XAxis, YAxis(left, %), YAxis(oil, reversed), Tooltip, Legend */}
                        <ReferenceLine yAxisId="left" y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
                        <Line yAxisId="left" dataKey="yoy" name="在庫名 YoY %" ... isAnimationActive={false} />
                        <Line yAxisId="oil" dataKey="oil_price" name="WTI原油 (USD/bbl, 反転)" ... isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* 前月比バーチャート */}
                {viewMode === 'mom' && displayMode === 'chart' && (
                  <>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <ResponsiveContainer width="100%" height={400}>
                      <ComposedChart data={filteredMomChartData} margin={CHART_MARGIN}>
                        {/* CartesianGrid, XAxis, YAxis(%) */}
                        <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeDasharray="3 3" />
                        <Bar dataKey="mom" name="在庫名 前月比 (%)" fill={COLOR_MAIN} isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}

                {/* 前月比ヒートマップ（前年比ヒートマップは不要） */}
                {viewMode === 'mom' && displayMode === 'heatmap' && (
                  <MonthlyTable data={momHeatmapData} decimals={2} showLegend
                    helperText="※ 在庫名 前月比（週次データの月平均から算出, 単位: %）" />
                )}
              </>
            ),
          },
          {
            key: 'market_impact', label: 'マーケットインパクト',
            children: <MarketImpactTab indicatorId="..." />,
          },
        ]}
      />
    </ChartContainer>
    ```

    #### 必須import
    ```tsx
    import { Tabs, Tooltip, Button } from 'antd'
    import { AreaChartOutlined } from '@ant-design/icons'
    import {
      ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
      Tooltip as RechartsTooltip, Legend, ResponsiveContainer, ReferenceLine,
    } from 'recharts'
    import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'
    import { MonthlyTable } from '../../country/usa/common/MonthlyTable'
    import { useMarketBatchData } from '../../../hooks/useMarketData'
    import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CHART_MARGIN } from '../../country/usa/common/chartConstants'
    import MarketImpactTab from '../../indicator/MarketImpactTab'
    ```

    #### chartConstants.ts に必要なボタン設定
    `VIEW_MODE_BUTTON_CONFIGS` に以下のキーが登録済み（追加不要）:
    - `raw`: 水準ボタン（pink系）
    - `mom`: 前月比ボタン（blue系）
    - `yoy`: 前年比ボタン（green系）
    - `chart`: チャートボタン（amber系）
    - `heatmap`: ヒートマップボタン（purple系）

    #### 注意事項
    - **全ての `<Line>`, `<Bar>`, `<Area>` に `isAnimationActive={false}` を必ず付ける**（→ 項目24参照）
    - **前年比ヒートマップは作成しない**（ユーザー明示: 不要）
    - **チャート/ヒートマップ切替は `viewMode === 'mom'` の時のみ表示**
    - **チャートmarginは `CHART_MARGIN` を使用**（`chartConstants.ts` からimport、ハードコード禁止）
    - **MoMバーチャートには `ReferenceLine y={0}` を必ず追加**（ゼロライン）
    - **前年比チャートにも `ReferenceLine y={0}` を追加**
    - **WTI原油オーバーレイは水準・前年比モードのみ**（MoMバーチャートには不要）
    - **`showPeriodSelector={false}`**: ChartContainer側のPeriodSelectorは非表示。各viewModeブロック内でPeriodSelectorを個別表示

    #### 参考実装:
    - 複数系列（合計/商業在庫/SPR）: `frontend/src/components/market/energy/WeeklyCrudeOilInventoriesChart.tsx`
    - 単一系列 + WTI: `frontend/src/components/market/energy/CushingInventoryChart.tsx`
    - 単一系列 + WTI: `frontend/src/components/market/energy/DistillateFuelInventoriesChart.tsx`
    - 複数系列（ガソリン+精製稼働率+WTI）: `frontend/src/components/market/energy/UsGasolineRefineryChart.tsx`

    #### バックエンドサービスの特徴:
    - ダッシュボードローダー不要（市場カテゴリは個別APIエンドポイント）
    - ルーター: `backend/routers/market.py` にエンドポイント追加
    - Redisキー: `market:{snake_case}:data`
    - EIA XLSパース: `xlrd` ライブラリ使用（OLE2形式のため `openpyxl` は不可）
    - YoY計算: 364日前 ±7日のfuzzyマッチで前年同週を検索
    - 参考: `backend/services/market/distillate_fuel_inventories_service.py`

24. **Rechartsの`<Line>` `<Bar>` `<Area>`に`isAnimationActive={false}`を付け忘れる**
    - **問題**: Rechartsのデフォルトではアニメーションが有効。チャートが多い画面でアニメーションが動くとUX低下
    - **症状**: チャート表示時に線やバーがアニメーション付きで描画される
    - **ルール**: **全ての `<Line>`, `<Bar>`, `<Area>` 要素に `isAnimationActive={false}` を必ず付ける**
    - **チェック方法**:
      ```bash
      # isAnimationActiveが付いていないLine/Bar/Area要素を検索
      rg '<(Line|Bar|Area)\b' --glob '*.tsx' path/to/file.tsx | grep -v 'isAnimationActive'
      ```
    - **注意**: `.map()` で動的にLine/Barを生成する場合も忘れずに付ける
      ```tsx
      // ❌ 忘れがち
      {series.map((s) => (
        <Line key={s.key} dataKey={s.key} stroke={s.color} dot={false} connectNulls />
      ))}

      // ✅ 正しい
      {series.map((s) => (
        <Line key={s.key} dataKey={s.key} stroke={s.color} dot={false} connectNulls isAnimationActive={false} />
      ))}
      ```
    - **ヘルパー関数で`<Line>`を返す場合も忘れずに付ける**:
      ```tsx
      // renderPrevLines等のヘルパー関数内のLineにも isAnimationActive={false} を付ける
      const renderPrevLines = (fields) => {
        return fields.map(f => (
          <Line key={f.prevKey} dataKey={f.prevKey} ... isAnimationActive={false} />
        ))
      }
      ```

25. **正負スタック棒グラフで`stackOffset="sign"`を使わない**
    - **問題**: 輸出（正値）と輸入（負値）のような正負のスタック棒グラフで、別々の`stackId`を使うとゼロ付近にギャップができる
    - **症状**: 正の棒と負の棒がゼロラインで接しない、見た目が不自然
    - **解決策**: `ComposedChart`に`stackOffset="sign"`を指定し、全バーを同一`stackId`にする
      ```tsx
      // ❌ NG: 別々のstackId → ゼロ付近にギャップ
      <ComposedChart data={data}>
        <Bar dataKey="export" stackId="export" />
        <Bar dataKey="neg_import" stackId="import" />
      </ComposedChart>

      // ✅ OK: stackOffset="sign" + 同一stackId
      <ComposedChart data={data} stackOffset="sign">
        <Bar dataKey="export" stackId="a" />
        <Bar dataKey="neg_import" stackId="a" />  {/* 負値は自動で下方向にスタック */}
      </ComposedChart>
      ```
    - **データ準備**: 輸入値を負値に変換してフロントエンドで保持
      ```tsx
      const chartData = useMemo(() => {
        return data.map(d => ({
          ...d,
          neg_import_pipeline: d.import_pipeline != null ? -d.import_pipeline : null,
          neg_import_lng: d.import_lng != null ? -d.import_lng : null,
        }))
      }, [data])
      ```
    - **参考実装**:
      - 天然ガス輸出入: `frontend/src/components/market/energy/UsNaturalGasTradeChart.tsx`
      - 投資部門別売買: `frontend/src/components/market/equities/JpxInvestorTradingChart.tsx`

26. **HTMLスクレイピングの正規表現でタグをまたいだマッチに`re.DOTALL`を忘れる**
    - **問題**: EIAの次回発表日等のHTMLスクレイピングで、ラベルと値が別タグにまたがっている場合に正規表現がマッチしない
    - **症状**: `next_release`が常に`None`を返す
    - **原因**: HTMLが以下のように改行・タブ・別タグで分かれている:
      ```html
      Next Release Date:</span> <span class="date">
      		March 26, 2026		</span>
      ```
    - **解決策**: `re.DOTALL`フラグを使い、`.`が改行にもマッチするようにする
      ```python
      # ❌ NG: re.DOTALLなし → 改行をまたげない
      match = re.search(r'Next Release Date:\s*(\w+ \d+,\s*\d{4})', resp.text)

      # ✅ OK: re.DOTALLあり + タグまたぎ対応
      match = re.search(
          r'Next Release Date:.*?<span[^>]*class="date"[^>]*>\s*'
          r'(\w+ \d+,\s*\d{4})',
          resp.text,
          re.DOTALL,
      )
      ```
    - **実装例**: `backend/services/market/us_natural_gas_trade_service.py`

27. **市場カテゴリ（/markets）のナビゲーションは`marketData.tsx`に追加する**
    - **問題**: `/markets`配下のチャートのナビゲーションを`countryData.tsx`に追加しようとしてしまう
    - **正しいファイル**: `frontend/src/constants/marketData.tsx`
    - **国別ダッシュボード（/country/...）**: `countryData.tsx` に追加
    - **市場ダッシュボード（/markets）**: `marketData.tsx` に追加
    - **追加例**:
      ```tsx
      // marketData.tsx の該当カテゴリ（energy, equities, commodities等）の subcategories に追加
      { code: 'natural-gas-trade', name: '天然ガス輸出入' },
      ```
    - **`code`はチャートの`<div id="...">`と一致させる**:
      ```tsx
      // EnergyCharts.tsx
      <div id="natural-gas-trade"><UsNaturalGasTradeChart /></div>
      ```

---

## 参考ファイル

実装時は以下の既存ファイルを参考にしてください：

- サービス: `backend/services/switzerland/ch_unemployment_rate_service.py`
- ローダー: `backend/services/dashboard/loaders/switzerland_employment.py`
- チャート: `frontend/src/components/country/switzerland/consumer/KofBarometerChart.tsx`
- 型定義: `frontend/src/hooks/useDashboardData.ts`
- オーバーレイ: `frontend/src/constants/overlayConfig.ts`
- EIAエネルギーチャート: `frontend/src/components/market/energy/WeeklyCrudeOilInventoriesChart.tsx`
- 正負スタック棒グラフ: `frontend/src/components/market/energy/UsNaturalGasTradeChart.tsx`
- 天然ガス貯蔵量（Pattern E + 天然ガス価格オーバーレイ）: `frontend/src/components/market/energy/UsNaturalGasStorageChart.tsx`
- 市場ナビゲーション: `frontend/src/constants/marketData.tsx`
