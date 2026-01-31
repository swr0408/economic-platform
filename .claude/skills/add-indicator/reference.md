# 経済指標実装リファレンス

このドキュメントは指標実装時の参考資料です。

---

## 1. 既存ファイル参照先

### バックエンド

| 種類 | 参考ファイル |
|------|-------------|
| サービス（API取得） | `backend/services/switzerland/ch_unemployment_rate_service.py` |
| サービス（DB取得） | `backend/services/usa/ism_manufacturing_service.py` |
| サービス（Excel取得） | `backend/services/switzerland/ch_unemployment_rate_service.py` |
| ダッシュボードローダー | `backend/services/dashboard/loaders/switzerland_employment.py` |
| FMPユーティリティ | `backend/services/switzerland/fmp_next_release_utils.py` |

### フロントエンド

| 種類 | 参考ファイル |
|------|-------------|
| チャート（単一系列） | `frontend/src/components/country/switzerland/consumer/KofBarometerChart.tsx` |
| チャート（複数系列） | `frontend/src/components/country/usa/economy/ISMManufacturingChart.tsx` |
| チャート（棒グラフ） | `frontend/src/components/country/usa/inflation/CPICategoriesChart.tsx` |
| 型定義 | `frontend/src/hooks/useDashboardData.ts` |
| オーバーレイ設定 | `frontend/src/constants/overlayConfig.ts` |

---

## 2. キャッシュキー命名規則

```
{country}:{snake_case}:data
```

例：
- `switzerland:ch_unemployment_rate:data`
- `usa:ism_manufacturing:data`
- `japan:boj_tankan:data`

---

## 3. ファイルキャッシュパス

```
backend/data/cache/{country}/{category}/{snake_case}_cache.json
```

例：
- `backend/data/cache/switzerland/employment/ch_unemployment_rate_cache.json`
- `backend/data/cache/usa/economy/ism_manufacturing_cache.json`

---

## 4. APIレスポンス標準形式

```json
{
  "data": [
    {"date": "2024-01-01", "value": 2.3},
    {"date": "2024-02-01", "value": 2.4}
  ],
  "latest": {"date": "2024-02-01", "value": 2.4},
  "metadata": {
    "source": "BFS (Federal Statistical Office)",
    "indicator": "Unemployment Rate",
    "description": "スイス失業率",
    "unit": "%"
  },
  "next_release": "2024-03-07T08:15:00+01:00",
  "cached": true,
  "source": "redis",
  "last_updated": "2024-02-07T18:30:00+09:00"
}
```

---

## 5. FMPマッピング登録

### indicator_event_mapping テーブル

```sql
INSERT INTO indicator_event_mapping
(econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
VALUES
('ch_unemployment_rate', '失業率', 'CH', 'monthly', '{"Unemployment Rate"}', true);
```

### 国コード

| 国 | コード |
|----|--------|
| アメリカ | US |
| 日本 | JP |
| ユーロ圏 | EU |
| イギリス | GB |
| スイス | CH |
| ドイツ | DE |
| フランス | FR |

---

## 6. チャートコンポーネント共通フック

### useSortedData
データを日付昇順にソート

```tsx
const chartData = useSortedData(rawChartData)
```

### usePeriodFiltering
期間でフィルタリング

```tsx
const filteredData = usePeriodFiltering(chartData, {
  selectedPeriod: currentPeriod,
  defaultStartYear: 2015,
})
```

### useViewModePeriodManagement
ビューモード毎の期間管理

```tsx
const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
  default: 'default',
})
```

### useMonthlyTableData
テーブル用データ変換

```tsx
const tableData = useMonthlyTableData(chartData, 'value')
```

### useHiddenSeries
凡例クリックで系列非表示

```tsx
const { hiddenSeries, toggleSeries } = useHiddenSeries()
```

---

## 7. 共通コンポーネント

### SimpleLatestValueBox
最新値を表示

```tsx
<SimpleLatestValueBox
  label="指標名"
  value={latestValue?.value}
  date={latestValue?.date}
  format="number" // "number" | "percent" | "currency"
  decimals={1}
  valueColor="#DC143C"
  nextRelease={data.next_release}
/>
```

### StandardLineChart
折れ線グラフ

```tsx
<StandardLineChart
  data={filteredData}
  lines={[
    { dataKey: 'value', color: '#2196f3', name: '系列名' },
  ]}
  yAxisFormatter={(v) => `${v}%`}
  tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
  yDomain={['dataMin - 1', 'dataMax + 1']}
  showZeroLine={false}
/>
```

### StandardBarChart
棒グラフ

```tsx
<StandardBarChart
  data={filteredData}
  bars={[
    { dataKey: 'value', color: '#2196f3', name: '系列名' },
  ]}
  yAxisFormatter={(v) => `${v}%`}
  tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
/>
```

### MarketImpactTab
マーケットインパクトタブ

```tsx
<MarketImpactTab indicatorId="ch_unemployment_rate" />
```

---

## 8. 色パレット

### 国別カラー

| 国 | 色 |
|----|----|
| アメリカ | `#1E88E5`（青） |
| 日本 | `#E53935`（赤） |
| ユーロ圏 | `#43A047`（緑） |
| イギリス | `#5E35B1`（紫） |
| スイス | `#DC143C`（クリムゾン） |

### 系列カラー

```typescript
const COLORS = {
  primary: '#2196f3',   // 青
  secondary: '#4caf50', // 緑
  tertiary: '#ff9800',  // オレンジ
  quaternary: '#9c27b0', // 紫
  quinary: '#ef5350',   // 赤
}
```

---

## 9. よくあるエラーと対処

### 画面に表示されない

1. ダッシュボードローダーの `EXPECTED_KEYS` に追加したか
2. ローダーの `load_all()` に取得処理を追加したか
3. カテゴリチャートにコンポーネントを追加したか
4. 型定義を追加したか

### マーケットインパクトが表示されない

1. `MarketImpactTab` の `indicatorId` を確認
2. `econalpha_id` と一致しているか

### データ比較でエラー

1. `overlayConfig.ts` に追加したか
2. `apiEndpoint` に `/dashboard` を付けていないか
3. `dataKey` がAPIレスポンスのキーと一致しているか

### 次回発表日が表示されない

1. サービスで `get_next_release_by_pattern()` を呼んでいるか
2. FMPマッピングが登録されているか
3. `FMP_COUNTRY` と `FMP_EVENT_PATTERN` が正しいか

---

## 10. ダッシュボードキャッシュ無効化

新規指標追加後は必ず実行：

```bash
curl -X DELETE http://localhost:8000/api/{country}/{category}/dashboard/cache
```

例：
```bash
curl -X DELETE http://localhost:8000/api/switzerland/employment/dashboard/cache
```
