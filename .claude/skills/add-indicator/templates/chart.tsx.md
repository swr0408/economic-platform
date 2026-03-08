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
                  {/* 期間選択 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く（{indicator_name_ja}）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s={econalpha_id}', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

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

## 前月比/前期比 + 前年比 切り替え（チャート＋ヒートマップパターン）★推奨

**重要**: 総合/コアなど複数系列がある前月比/前期比＋前年比指標の標準レイアウト。
CPI、PPI、小売売上高など、多くの指標がこのパターンに従う。

### レイアウト構造

```
┌─────────────────────────────────────────────┐
│  LatestValueBox（総合・コア等の最新値表示）  │
├─────────────────────────────────────────────┤
│  上段: [前期比/前月比 | 前年比]  [データ比較] │  ← ViewModeButtonGroup
│  下段: [チャート | ヒートマップ]              │  ← 前期比/前月比のときのみ表示
├─────────────────────────────────────────────┤
│  前年比 → 折れ線グラフ（全系列同時表示）     │  ← useHiddenSeries で凡例切替
│  前期比チャート → DataTypeButtonGroup        │  ← 総合/コア/その他の切替
│                   + PeriodSelector + 棒グラフ │
│  前期比ヒートマップ → テーブル内切替          │  ← 総合/コア/その他の切替
└─────────────────────────────────────────────┘
```

### ポイント

- **上段**: `ViewModeButtonGroup` で `前期比（or 前月比）| 前年比` を切り替え
- **下段**: `ViewModeButtonGroup` で `チャート | ヒートマップ` を切り替え（前期比/前月比のときのみ）
- **前年比**: チャートのみ（折れ線で全体+コア等を同時表示、`useHiddenSeries` で凡例クリック切替）
- **前月比/前期比チャート**: `DataTypeButtonGroup` で 総合/コア/その他を切替 + `StandardBarChart`
- **前月比/前期比ヒートマップ**: `MonthlyTableWithDataTypes` / `QuarterlyTableWithDataTypes` で 全体/コア/その他切替
- 指標によって `前月比`（monthly）か `前期比`（quarterly）かが異なる。ビューモードの `label` を適切に設定する

### 月次指標の場合（前月比/前年比）

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
  useHiddenSeries,
  useMultiValueMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { {PascalCase}Data } from '../../../../hooks/useDashboardData'

interface {PascalCase}ChartProps {
  data: {PascalCase}Data | null
}

interface ChartDataPoint {
  date: string
  total_yoy: number | null
  core_yoy: number | null
  total_mom: number | null
  core_mom: number | null
}

const COLORS = {
  total: '#2563eb',   // 総合（青）
  core: '#dc2626',    // コア（赤）
}

// ===== 上段: 指標種別 =====
type DataType = 'mom' | 'yoy'

const DATA_TYPE_OPTIONS: { mode: DataType; label: string }[] = [
  { mode: 'mom', label: '前月比' },
  { mode: 'yoy', label: '前年比' },
]

// ===== 下段: 表示形式（前月比のときのみ） =====
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// ===== データタイプ（前月比チャート＋ヒートマップ用） =====
type MomDataType = 'total' | 'core'

const MOM_DATA_TYPE_OPTIONS: { type: MomDataType; label: string }[] = [
  { type: 'total', label: '総合' },
  { type: 'core', label: 'コア' },
]

export default function {PascalCase}Chart({ data }: {PascalCase}ChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataType, setDataType] = useState<DataType>('mom')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [momDataType, setMomDataType] = useState<MomDataType>('total')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataType, {
    mom: 3,
    yoy: 'default',
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []
    return data.data
      .filter((item) => item.total_mom !== null || item.total_yoy !== null)
      .map((item) => ({
        date: item.date,
        total_yoy: item.total_yoy,
        core_yoy: item.core_yoy,
        total_mom: item.total_mom,
        core_mom: item.core_mom,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2018,
  })

  // ヒートマップ用データ
  const momTableData = useMultiValueMonthlyTableData(
    sortedData,
    {
      total: (item: ChartDataPoint) => item.total_mom,
      core: (item: ChartDataPoint) => item.core_mom,
    },
    10
  )

  const hasData = sortedData.length > 0
  if (data === null) return <LoadingChart title="{indicator_name_ja}" />
  if (!hasData) return (
    <ChartContainer title="{indicator_name_ja}" showPeriodSelector={false} showDataSource={false}>
      <NoDataMessage />
    </ChartContainer>
  )

  const latest = data?.latest

  return (
    <div id="{snake_case}">
      <ChartContainer
        title="{indicator_name_ja}"
        showPeriodSelector={false}
        dataSource="{data_source_name}"
        sourceUrl="{data_source_url}"
      >
        {/* 最新値表示（複数系列） */}
        <LatestValueBox
          items={[
            { label: '総合', value: latest?.total_yoy, color: COLORS.total, format: 'percent' },
            { label: 'コア（前年比）', value: latest?.core_yoy, color: COLORS.core, format: 'percent' },
          ]}
          date={latest?.date}
          nextRelease={data?.next_release ? { date: data.next_release.date } : undefined}
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_TYPE_OPTIONS} currentMode={dataType} onChange={setDataType} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s={econalpha_id}', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataType === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* ===== 前月比チャート（棒グラフ）===== */}
                  {dataType === 'mom' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup options={MOM_DATA_TYPE_OPTIONS} currentType={momDataType} onChange={setMomDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          momDataType === 'total'
                            ? { dataKey: 'total_mom', color: COLORS.total, name: '総合（前月比）' }
                            : { dataKey: 'core_mom', color: COLORS.core, name: 'コア（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                      />
                    </>
                  )}

                  {/* ===== 前月比ヒートマップ ===== */}
                  {dataType === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes<MomDataType>
                      data={momTableData}
                      dataTypes={MOM_DATA_TYPE_OPTIONS}
                      selectedType={momDataType}
                      onTypeChange={setMomDataType}
                      decimals={1}
                      helperText="※ 直近10年間の前月比データ（単位: %）"
                      formatValue={(v) => {
                        if (v === null || v === undefined) return '-'
                        return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`
                      }}
                    />
                  )}

                  {/* ===== 前年比チャート（折れ線グラフ・全系列同時表示）===== */}
                  {dataType === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'total_yoy', color: COLORS.total, name: '総合（前年比）', hide: hiddenSeries.has('total_yoy') },
                          { dataKey: 'core_yoy', color: COLORS.core, name: 'コア（前年比）', hide: hiddenSeries.has('core_yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        showZeroLine={true}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="{econalpha_id}" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
```

### 四半期指標の場合（前期比/前年比）

月次を四半期に変更するポイント:
- `mom` → `qoq`、`前月比` → `前期比`
- `useMultiValueMonthlyTableData` → `useMultiValueQuarterlyTableData`
- `MonthlyTableWithDataTypes` → `QuarterlyTableWithDataTypes`
- `useViewModePeriodManagement` の期間: `{ qoq: 5, yoy: 'default' }`（四半期は5年表示）
- X軸フォーマッタ: `formatQuarterLabel` を使用

```tsx
// 四半期で変わる部分のみ抜粋

import { useMultiValueQuarterlyTableData } from '../../usa/common/useChartData'
import { QuarterlyTableWithDataTypes } from '../../usa/common/QuarterlyTable'

type DataType = 'qoq' | 'yoy'
const DATA_TYPE_OPTIONS: { mode: DataType; label: string }[] = [
  { mode: 'qoq', label: '前期比' },
  { mode: 'yoy', label: '前年比' },
]

// ヒートマップ用データ
const qoqTableData = useMultiValueQuarterlyTableData(
  sortedData,
  {
    total: (item: ChartDataPoint) => item.total_qoq,
    core: (item: ChartDataPoint) => item.core_qoq,
  },
  10
)

// ヒートマップ表示
{dataType === 'qoq' && displayMode === 'heatmap' && (
  <QuarterlyTableWithDataTypes<QoqDataType>
    data={qoqTableData}
    dataTypes={QOQ_DATA_TYPE_OPTIONS}
    selectedType={qoqDataType}
    onTypeChange={setQoqDataType}
    decimals={1}
    helperText="※ 直近10年間の前期比データ（単位: %、季節調整済み）"
    formatValue={(v) => {
      if (v === null || v === undefined) return '-'
      return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`
    }}
  />
)}
```

### 3系列以上がある場合

総合/コア/コアコアのように3つ以上の系列がある場合:

```tsx
type MomDataType = 'total' | 'core' | 'core_core'

const MOM_DATA_TYPE_OPTIONS: { type: MomDataType; label: string }[] = [
  { type: 'total', label: '総合' },
  { type: 'core', label: 'コア' },
  { type: 'core_core', label: 'コアコア' },
]

// 前年比チャートでは全系列を同時表示
lines={[
  { dataKey: 'total_yoy', color: COLORS.total, name: '総合（前年比）', hide: hiddenSeries.has('total_yoy') },
  { dataKey: 'core_yoy', color: COLORS.core, name: 'コア（前年比）', hide: hiddenSeries.has('core_yoy') },
  { dataKey: 'core_core_yoy', color: COLORS.core_core, name: 'コアコア（前年比）', hide: hiddenSeries.has('core_core_yoy') },
]}
```

**参考実装**:
- `frontend/src/components/country/newzealand/consumer/NzRetailSalesChart.tsx`（四半期・2系列）
- `frontend/src/components/country/australia/inflation/AuQuarterlyCpiChart.tsx`（四半期・4系列）
- `frontend/src/components/country/japan/price/NationalCPIChart.tsx`（月次・3系列）
- `frontend/src/components/country/usa/inflation/CPIChart.tsx`（月次・2系列）

---

## 前年比/前月比切り替え（単一系列・MoM棒グラフ＋テーブル表示パターン）

**重要**: 総合のみ（単一系列）の場合に使用。GermanyRetailSalesChart、CHRetailTradeChartと同じ形式。
複数系列がある場合は上の「チャート＋ヒートマップパターン」を使用すること。

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

## 複数系列の場合（全て同時表示・凡例クリック切替）

**重要**: 複数系列を同時表示する場合は以下のパターンを使用してください。
- `LATEST_VALUE_BOX_STYLE` で最新値を横並びに表示
- `useHiddenSeries` と `onLegendClick` で凡例クリックによる表示/非表示切替
- `SimpleLatestValueBox` は使用しない（単一系列用のため）

```tsx
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useHiddenSeries,  // ← 凡例クリック用
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'  // ← 最新値ボックス用

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { {PascalCase}Data } from '../../../../hooks/useDashboardData'

interface {PascalCase}ChartProps {
  data: {PascalCase}Data | null
}

interface ChartDataPoint {
  date: string
  series1: number | null
  series2: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  series1: '#DC143C',  // 赤
  series2: '#1890ff',  // 青
}

export default function {PascalCase}Chart({ data }: {PascalCase}ChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  // 凡例クリックで非表示にするシリーズを管理
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // propsのデータをチャート用に変換（両データをマージ）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const dateMap: Record<string, ChartDataPoint> = {}

    // 系列1データをマージ
    data.series1_data?.forEach((item) => {
      if (!dateMap[item.date]) {
        dateMap[item.date] = {
          date: item.date,
          series1: null,
          series2: null,
        }
      }
      dateMap[item.date].series1 = item.value
    })

    // 系列2データをマージ
    data.series2_data?.forEach((item) => {
      if (!dateMap[item.date]) {
        dateMap[item.date] = {
          date: item.date,
          series1: null,
          series2: null,
        }
      }
      dateMap[item.date].series2 = item.value
    })

    // 日付順にソート
    return Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2018,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestSeries1 = data?.latest_series1
  const latestSeries2 = data?.latest_series2

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
        {/* 最新値表示（複数系列） - LATEST_VALUE_BOX_STYLEを使用 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 系列1 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.series1,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>系列1</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.series1 }}>
              {latestSeries1?.value?.toFixed(1) ?? '-'}
            </span>
          </div>

          {/* 系列2 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.series2,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>系列2</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.series2 }}>
              {latestSeries2?.value?.toFixed(1) ?? '-'}
            </span>
          </div>

          {/* 日付・次回発表情報（右側に配置） */}
          <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-end', fontSize: 11, color: '#8c8c8c' }}>
            {latestSeries1?.date && <div>{latestSeries1.date}</div>}
            {data.next_release && (
              <div>
                次回発表: {data.next_release.date}{data.next_release.label && ` - ${data.next_release.label}`}
              </div>
            )}
          </div>
        </div>

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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s={econalpha_id}_series1&s={econalpha_id}_series2', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* グラフ（凡例クリックで表示切替） */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'series1', color: COLORS.series1, name: '系列1', hide: hiddenSeries.has('series1') },
                      { dataKey: 'series2', color: COLORS.series2, name: '系列2', hide: hiddenSeries.has('series2') },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
                    yDomain={[30, 70]}
                    showZeroLine={false}
                    showFiftyLine={true}  // PMI等の場合
                    onLegendClick={handleLegendClick}  // ← 凡例クリックハンドラ
                  />

                  {/* 説明文 */}
                  <div style={{ marginTop: 8, fontSize: 11, color: '#888' }}>
                    ※凡例クリックで表示/非表示切替
                  </div>
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
- `frontend/src/components/country/switzerland/economy/ChPmiChart.tsx`（製造業PMI・サービス業PMI）
- `frontend/src/components/country/usa/economy/SPPMIChart.tsx`（S&P Global PMI 3系列）

---

## 複数系列の切り替え表示（グループ切り替えパターン）

**重要**: 系列をグループで切り替え表示する場合は必ず `ViewModeButtonGroup` を使用してください。
`Radio.Group` は使用しないでください（レイアウト統一のため）。

```tsx
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
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
  ViewModeButtonGroup,  // ← 必ずこれを使用
} from '../../usa/common/ChartComponents'

// グラフの色
const COLORS = {
  group1_series1: '#FF6B6B',
  group1_series2: '#FF8E53',
  group2_series1: '#4169E1',
  group2_series2: '#00CED1',
}

// 表示モード
type ViewMode = 'all' | 'group1' | 'group2'

// ビューモード設定（ViewModeButtonGroup用）
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'all', label: '全て' },
  { mode: 'group1', label: 'グループ1' },
  { mode: 'group2', label: 'グループ2' },
]

export default function {PascalCase}Chart({ data }: {PascalCase}ChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('all')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 'default',
  })

  // ...データ変換処理...

  // 現在のビューモードに応じた最新値を取得
  const currentLatestValue = useMemo(() => {
    if (!latestValue) return null
    if (viewMode === 'group1') return latestValue.group1_series1
    if (viewMode === 'group2') return latestValue.group2_series1
    return latestValue.group1_series1 // all の場合
  }, [latestValue, viewMode])

  // 現在のビューモードに応じた色を取得
  const currentColor = useMemo(() => {
    if (viewMode === 'group1') return COLORS.group1_series1
    if (viewMode === 'group2') return COLORS.group2_series1
    return COLORS.group1_series1
  }, [viewMode])

  // 表示する系列を取得
  const getLines = () => {
    if (viewMode === 'group1') {
      return [
        { dataKey: 'group1_series1', color: COLORS.group1_series1, name: 'G1系列1' },
        { dataKey: 'group1_series2', color: COLORS.group1_series2, name: 'G1系列2' },
      ]
    } else if (viewMode === 'group2') {
      return [
        { dataKey: 'group2_series1', color: COLORS.group2_series1, name: 'G2系列1' },
        { dataKey: 'group2_series2', color: COLORS.group2_series2, name: 'G2系列2' },
      ]
    }
    // all
    return [
      { dataKey: 'group1_series1', color: COLORS.group1_series1, name: 'G1系列1' },
      { dataKey: 'group1_series2', color: COLORS.group1_series2, name: 'G1系列2' },
      { dataKey: 'group2_series1', color: COLORS.group2_series1, name: 'G2系列1' },
      { dataKey: 'group2_series2', color: COLORS.group2_series2, name: 'G2系列2' },
    ]
  }

  // 最新値ラベルを取得
  const getLatestLabel = () => {
    if (viewMode === 'group1') return '{indicator_name_ja}（グループ1）'
    if (viewMode === 'group2') return '{indicator_name_ja}（グループ2）'
    return '{indicator_name_ja}（グループ1）'
  }

  // ...（省略: ローディング・NoData処理）

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
          label={getLatestLabel()}
          value={currentLatestValue}
          date={latestValue?.date}
          format="percent"
          decimals={2}
          valueColor={currentColor}
          nextRelease={data.next_release}
        />

        {/* ビューモード切替 - ViewModeButtonGroupを必ず使用 */}
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={setViewMode}
        />

        {/* 期間セレクター・データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s={econalpha_id}_group1&s={econalpha_id}_group2', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={getLines()}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
          yDomain={['auto', 'auto']}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
```

**参考実装**:
- `frontend/src/components/country/switzerland/housing/CHMortgageRatesChart.tsx`（変動金利/固定金利の切り替え）

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
// 次回発表日の型（FMPから取得される形式）
export interface {PascalCase}NextRelease {
  date: string           // YYYY-MM-DD形式
  datetime_jst: string   // ISO8601形式（JST）
  time_jst: string       // HH:MM形式
  label: string          // 例: "Indicator Name (Jan)"
  estimate: number | null
}

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
  next_release?: {PascalCase}NextRelease | null  // ← オブジェクト型（stringではない）
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
