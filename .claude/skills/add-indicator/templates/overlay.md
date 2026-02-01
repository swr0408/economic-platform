# overlayConfig.ts テンプレート

データ比較機能に指標を追加する方法を説明します。

---

## ファイルパス

```
frontend/src/constants/overlayConfig.ts
```

---

## OVERLAY_INDICATORS への追加

`OVERLAY_INDICATORS` 配列に以下の形式で追加：

```typescript
// =========================================================================
// {category_ja} - {sub_category_ja}
// =========================================================================
{
  id: '{econalpha_id}',
  name: '{indicator_name_ja}',
  nameEn: '{indicator_name_en}',
  frequency: '{frequency}',
  country: '{country}',
  category: '{category}',
  subCategory: '{overlay_sub_category}',
  apiEndpoint: '/api/{country}/{category}',  // ※ /dashboardは付けない
  dataKey: '{snake_case}',
  valueField: 'value',  // データのフィールド名
  unit: '{unit}',
},
```

---

## 重要な注意点

### 1. apiEndpoint について

#### ダッシュボードAPI（カテゴリ単位で一括取得）

- **付けない**: `/dashboard` は自動で付与される
- **正しい例**: `apiEndpoint: '/api/usa/employment'`
- **間違い例**: `apiEndpoint: '/api/usa/employment/dashboard'`

`useOverlayData.ts` が自動で `/dashboard` を付与します。

#### 個別API（Direct API）

以下のパターンで始まるエンドポイントは個別APIとして認識され、`/dashboard`が付与されません：

- `/api/nyfed/`, `/api/fed-h15/`, `/api/cme/`
- `/api/japan/` 配下の多くのエンドポイント
- `/api/uk/boe-`, `/api/uk/ons-`
- `/api/eurozone/pmi`, `/api/eurozone/germany-pmi`, `/api/eurozone/france-pmi`
- `/api/switzerland/` 配下のすべてのエンドポイント

個別APIの場合：
- `dataKey: 'data'` （APIレスポンスの `data` 配列を参照）
- `valueField` で値フィールドを指定

```typescript
{
  id: 'foreign_currency_reserves_chf',
  name: '外貨準備（CHF）',
  nameEn: 'Foreign Currency Reserves (CHF)',
  frequency: 'monthly',
  country: 'switzerland',
  category: 'policy',
  subCategory: 'fed',
  apiEndpoint: '/api/switzerland/snb/foreign-currency-reserves',
  dataKey: 'data',  // APIレスポンスの data 配列
  valueField: 'chf',  // data配列内の各項目から取得するフィールド
  unit: 'M CHF',
},
```

### 2. dataKey について

APIレスポンスのキーと一致させる必要があります。

例えば、APIレスポンスが以下の場合：
```json
{
  "data": {
    "ch_unemployment_rate": {
      "data": [...],
      "latest": {...}
    }
  }
}
```

`dataKey: 'ch_unemployment_rate'` と指定します。

### 3. valueField について

データ配列内の値フィールド名を指定：

```typescript
// 単純なフィールド
valueField: 'value',
valueField: 'yoy',
valueField: 'mom',

// ネストしたフィールド（ドット記法）
valueField: 'weekly.nominal',
valueField: 'baseline.data',
```

### 4. nestedKey について

カテゴリ配列データ内の特定カテゴリを指定する場合：

```typescript
{
  id: 'sp_manufacturing_pmi',
  name: 'S&P製造業PMI',
  dataKey: 'sp_pmi',
  nestedKey: 'manufacturing',  // sp_pmi.manufacturing を参照
},
```

---

## frequency オプション

```typescript
frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly' | 'irregular'
```

---

## subCategory オプション

```typescript
// 政策
subCategory: 'interest_rate' | 'fed'

// 経済
subCategory: 'gdp' | 'sentiment' | 'production'

// 消費
subCategory: 'retail' | 'spending' | 'confidence'

// 雇用
subCategory: 'jobs' | 'claims' | 'wages'

// 物価
subCategory: 'cpi' | 'cpi_components' | 'ppi' | 'pce_deflator' | 'inflation_expectations'

// 住宅
subCategory: 'mortgage' | 'home_price' | 'starts' | 'sales' | 'permits'

// 市場
subCategory: 'forex_usd' | 'forex_jpy' | 'bond' | 'commodity_metal' | 'commodity_energy'
```

---

## 完全な追加例

```typescript
// =========================================================================
// スイス - 雇用
// =========================================================================
{
  id: 'ch_unemployment_rate',
  name: 'スイス失業率',
  nameEn: 'Switzerland Unemployment Rate',
  frequency: 'monthly',
  country: 'switzerland',
  category: 'employment',
  subCategory: 'jobs',
  apiEndpoint: '/api/switzerland/employment',
  dataKey: 'ch_unemployment_rate',
  valueField: 'value',
  unit: '%',
},
```

---

## チャートコンポーネントでの比較ボタン設定

チャートコンポーネント内で比較ボタンを追加する際：

```tsx
<Button
  icon={<AreaChartOutlined />}
  onClick={() => window.open('/compare?s={econalpha_id}', '_blank')}
>
  データ比較
</Button>
```

複数指標を初期選択する場合（最大6個）：

```tsx
onClick={() => window.open('/compare?s={econalpha_id}&s=related_indicator_1&s=related_indicator_2', '_blank')}
```

---

## デバッグ方法

比較ページでエラーが発生する場合：

1. **ブラウザのDevTools > Network** でAPIリクエストを確認
2. レスポンスの構造と `dataKey` が一致しているか確認
3. `valueField` が正しいフィールドを指しているか確認

よくあるエラー：
- `Cannot read property 'data' of undefined` → `dataKey` が間違っている
- グラフが表示されない → `valueField` が間違っている
- 404 エラー → `apiEndpoint` が間違っている
