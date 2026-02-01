# チャートコンポーネントテンプレート

以下のテンプレートを使用してチャートコンポーネントを作成してください。
`{変数}` の部分を入力フォームの値で置き換えてください。

---

## ファイルパス

```
frontend/src/components/country/{country}/{category}/{PascalCase}Chart.tsx
```

---

## テンプレートコード（単一系列・折れ線グラフ）

```tsx
/**
 * {indicator_name_ja} チャートコンポーネント
 *
 * {data_source_name}から{indicator_name_en}データを取得し、表示
 *
 * データ:
 * - {indicator_name_en}（{indicator_name_ja}）
 *
 * データソース:
 * - {data_source_name}
 *
 * 発表スケジュール:
 * - {release_pattern}
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { {PascalCase}Data } from '../../../../hooks/useDashboardData'

interface {PascalCase}ChartProps {
  data: {PascalCase}Data | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  main: '{chart_color}',
}

export default function {PascalCase}Chart({ data }: {PascalCase}ChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].value !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="{indicator_name_ja}" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="{indicator_name_ja}" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="{snake_case}-chart">
      <ChartContainer
        title="{indicator_name_ja}"
        showPeriodSelector={false}
        dataSource="{data_source_name}"
        sourceUrl="{data_source_url}"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="{indicator_name_ja}"
          value={latestValue?.value}
          date={latestValue?.date}
          format="{y_axis_format === 'percent' ? 'percent' : 'number'}"
          decimals={1}
          valueColor={COLORS.main}
          nextRelease={data.next_release}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* コントロールバー */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く（{indicator_name_ja}）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s={econalpha_id}', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.main, name: '{indicator_name_ja}' },
                    ]}
                    yAxisFormatter={(v) => `${v}{unit}`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}{unit}`}
                    yDomain={['dataMin - 1', 'dataMax + 1']}
                    showZeroLine={false}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="{econalpha_id}" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
```

---

## 前年比/前月比切り替えの場合（MoM/YoY toggle）

**重要**: 前年比/前月比の切り替えには `ViewModeButtonGroup` を使用してください。
`Radio.Group` は使用しないでください。

```tsx
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  ViewModeButtonGroup,  // ← 必ずこれを使用
} from '../../usa/common/ChartComponents'

// ...

type ViewMode = 'yoy' | 'mom'

export default function {PascalCase}Chart({ data }: {PascalCase}ChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: viewMode === 'mom' ? item.mom : item.yoy,
    }))
  }, [data, viewMode])

  // ... 以下同様 ...

  const chartTitle = viewMode === 'mom' ? '{indicator_name_ja}（前月比）' : '{indicator_name_ja}（前年比）'
  const overlayKey = viewMode === 'mom' ? '{econalpha_id}_mom' : '{econalpha_id}_yoy'

  return (
    // ...
    <>
      {/* YoY/MoM切替 - ViewModeButtonGroupを使用 */}
      <ViewModeButtonGroup
        currentMode={viewMode}
        onChange={(mode) => setViewMode(mode)}
        options={[
          { mode: 'yoy', label: '前年比' },
          { mode: 'mom', label: '前月比' },
        ]}
      />

      {/* コントロールバー */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        <Tooltip title={`比較ページを開く（${chartTitle}）`}>
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => window.open(`/compare?s=${overlayKey}`, '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* グラフ */}
      <StandardLineChart
        data={filteredData}
        lines={[
          { dataKey: 'value', color: COLORS.main, name: chartTitle },
        ]}
        yAxisFormatter={(v) => `${v}%`}
        tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
        yDomain={['dataMin - 2', 'dataMax + 2']}
        showZeroLine={true}
      />
    </>
  )
}
```

**MoM/YoYの型定義**:

```tsx
export interface {PascalCase}Item {
  date: string
  mom: number | null
  yoy: number | null
}
```

---

## 前年比/前月比切り替え（MoM棒グラフ＋テーブル表示パターン）

**重要**: 小売売上高など、MoMを棒グラフとテーブルの両方で表示する場合はこのパターンを使用。
GermanyRetailSalesChart、CHRetailTradeChartと同じ形式。

```tsx
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,  // テーブル用
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,  // MoM棒グラフ用
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'  // テーブル用

// ...

interface ChartDataPoint {
  date: string
  yoy: number
  mom: number
  [key: string]: unknown
}

const COLORS = {
  yoy: '#1890ff',  // 前年比（折れ線）
  mom: '#52c41a',  // 前月比（棒グラフ）
}

// ビューモードは3種類: yoy（折れ線）, mom_chart（棒グラフ）, mom_table（テーブル）
type ViewMode = 'yoy' | 'mom_chart' | 'mom_table'

export default function {PascalCase}Chart({ data }: {PascalCase}ChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_chart: 3,  // MoMチャートは3年表示
    mom_table: 'default',
  })

  // データ変換（yoyとmomの両方を保持）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      yoy: item.yoy ?? 0,
      mom: item.mom ?? 0,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom)

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // ...（省略: データなしの処理）

  return (
    <div id="{snake_case}-chart">
      <ChartContainer
        title="{indicator_name_ja}"
        showPeriodSelector={false}
        dataSource="{data_source_name}"
        sourceUrl="{data_source_url}"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={viewMode === 'yoy' ? latest?.yoy : latest?.mom}
          valueColor={viewMode === 'yoy' ? COLORS.yoy : COLORS.mom}
          date={latest?.date}
          nextRelease={data.next_release}
          format="percent"
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 3ボタン切替 */}
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode as ViewMode)}
                    options={[
                      { mode: 'yoy', label: '前年比' },
                      { mode: 'mom_chart', label: '前月比' },
                      { mode: 'mom_table', label: '前月比（テーブル）' },
                    ]}
                  />

                  {/* 期間セレクター（テーブル以外で表示） */}
                  {(viewMode === 'yoy' || viewMode === 'mom_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s={econalpha_id}_yoy', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'mom_table' && <MonthlyTable data={momTableData} />}

                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '{indicator_name_ja}（前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                    />
                  )}

                  {viewMode === 'mom_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '{indicator_name_ja}（前月比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="{econalpha_id}" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
```

**参考実装**:
- `frontend/src/components/country/eurozone/consumer/GermanyRetailSalesChart.tsx`
- `frontend/src/components/country/switzerland/consumer/CHRetailTradeChart.tsx`

---

## 棒グラフの場合

`StandardLineChart` を `StandardBarChart` に変更：

```tsx
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardBarChart,  // ← 変更
} from '../../usa/common/ChartComponents'

// ...

<StandardBarChart
  data={filteredData}
  bars={[
    { dataKey: 'value', color: COLORS.main, name: '{indicator_name_ja}' },
  ]}
  yAxisFormatter={(v) => `${v}{unit}`}
  tooltipValueFormatter={(v) => `${v.toFixed(1)}{unit}`}
/>
```

---

## 複数系列の場合

```tsx
const COLORS = {
  series1: '#2196f3',
  series2: '#4caf50',
  series3: '#ff9800',
}

// rawChartData で複数フィールドをマッピング
const rawChartData = useMemo<ChartDataPoint[]>(() => {
  if (!data?.data) return []

  return data.data.map((item) => ({
    date: item.date,
    value1: item.value1,
    value2: item.value2,
    value3: item.value3,
  }))
}, [data])

// グラフ
<StandardLineChart
  data={filteredData}
  lines={[
    { dataKey: 'value1', color: COLORS.series1, name: '系列1' },
    { dataKey: 'value2', color: COLORS.series2, name: '系列2' },
    { dataKey: 'value3', color: COLORS.series3, name: '系列3' },
  ]}
  yAxisFormatter={(v) => `${v}`}
  tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
/>
```

---

## テーブル表示を追加する場合

```tsx
import { MonthlyTable } from '../../usa/common/ChartComponents'
import { useMonthlyTableData } from '../../usa/common/useChartData'
import ViewModeButtonGroup from '../../../common/ViewModeButtonGroup'

// ビューモード状態
const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart')

// テーブル用データ変換
const tableData = useMonthlyTableData(chartData, 'value')

// ビューモード切替ボタン
<ViewModeButtonGroup
  viewMode={viewMode}
  onChange={setViewMode}
  showTable={true}
/>

// テーブル表示
{viewMode === 'table' && (
  <MonthlyTable
    data={tableData}
    valueFormatter={(v) => v.toFixed(1)}
    unit="{unit}"
  />
)}
```

---

## 型定義の追加

`frontend/src/hooks/useDashboardData.ts` に以下を追加：

```tsx
// {indicator_name_ja}データの型
export interface {PascalCase}Data {
  data: {PascalCase}Item[]
  latest: {PascalCase}Item | null
  metadata: {
    source: string
    indicator: string
    description: string
    unit: string
  }
  next_release: string | null
}

export interface {PascalCase}Item {
  date: string
  value: number
}

// 既存の {Country}{Category}Data に追加
export interface {Country}{Category}Data {
  // ... 既存フィールド ...
  {snake_case}: {PascalCase}Data | null  // ← 追加
}
```

---

## カテゴリチャートへの統合

`frontend/src/components/country/{country}/{Country}{Category}Charts.tsx` に追加：

```tsx
import {PascalCase}Chart from './{category}/{PascalCase}Chart'

// コンポーネント内で
<{PascalCase}Chart data={data?.{snake_case} ?? null} />
```
