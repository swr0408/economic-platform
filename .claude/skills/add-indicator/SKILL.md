---
name: add-indicator
description: "新規経済指標を追加する。FMPマッピング、バックエンド、フロントエンド、データ比較機能を含む完全実装"
argument-hint: "[入力フォーム形式で指定]"
disable-model-invocation: true
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
show_table: false             # テーブル表示するか
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

#### 2.5 データ比較機能追加（add_to_overlay: true の場合）
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

---

## 参考ファイル

実装時は以下の既存ファイルを参考にしてください：

- サービス: `backend/services/switzerland/ch_unemployment_rate_service.py`
- ローダー: `backend/services/dashboard/loaders/switzerland_employment.py`
- チャート: `frontend/src/components/country/switzerland/consumer/KofBarometerChart.tsx`
- 型定義: `frontend/src/hooks/useDashboardData.ts`
- オーバーレイ: `frontend/src/constants/overlayConfig.ts`
