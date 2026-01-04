/**
 * シカゴ連銀小売指数（CARTS）チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CartsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  TOOLTIP_STYLE,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
} from '../common/chartConstants'
import {
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
  useHiddenSeries,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
} from '../common/ChartComponents'


// =============================================================================
// 型定義
// =============================================================================

interface CartsChartProps {
  data: CartsData | null
}

// カラー設定
const COLORS = {
  nominal: '#2f54eb',
  real: CHART_COLORS.positive,
}

// 系列名
const SERIES_NAMES = {
  nominal: '名目値',
  real: '実質値（2017年基準）',
}

// =============================================================================
// カスタムTooltip（両方の値を常に表示）
// =============================================================================

interface DataItem {
  date: string
  nominalB: number | null
  realB: number | null
}

interface CartsTooltipProps {
  active?: boolean
  label?: string
  data?: DataItem[]
}

function CartsTooltip({ active, label, data }: CartsTooltipProps) {
  if (!active || !label) return null

  const dataPoint = data?.find((d: DataItem) => d.date === label)
  if (!dataPoint) return null

  const items = [
    { name: SERIES_NAMES.nominal, value: dataPoint.nominalB, color: COLORS.nominal },
    { name: SERIES_NAMES.real, value: dataPoint.realB, color: COLORS.real },
  ]

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatDateLabelJP(label)}
      </div>
      {items.map((item, index) => (
        <div
          key={index}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 4,
            fontSize: 13,
            padding: '4px 12px',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: 2,
                backgroundColor: item.color,
                marginRight: 6,
              }}
            />
            {item.name}
          </span>
          <span style={{ fontWeight: 500, color: item.color }}>
            {item.value !== null && item.value !== undefined ? `$${item.value.toFixed(1)}B` : 'N/A'}
          </span>
        </div>
      ))}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CartsChart({ data }: CartsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 週次データを月次データに集約
  const monthlyData = useMemo(() => {
    if (!data?.weekly?.data || data.weekly.data.length === 0) return []

    const monthGroups: Record<string, typeof data.weekly.data[0]> = {}

    data.weekly.data.forEach((item) => {
      const date = new Date(item.date)
      const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

      if (!monthGroups[monthKey] || new Date(item.date) > new Date(monthGroups[monthKey].date)) {
        monthGroups[monthKey] = item
      }
    })

    return Object.entries(monthGroups)
      .map(([monthKey, item]) => ({
        date: `${monthKey}-01`,
        monthKey,
        nominal: item.nominal,
        real: item.real,
        nominalB: item.nominal ? item.nominal / 1000 : null,
        realB: item.real ? item.real / 1000 : null,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(monthlyData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = monthlyData.length > 0

  if (data === null) {
    return <LoadingChart title="シカゴ連銀小売指数（CARTS）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="シカゴ連銀小売指数（CARTS）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.weekly?.latest

  // ドル値をB単位でフォーマット
  const formatDollarB = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A'
    return `$${(value / 1000).toFixed(1)}B`
  }

  return (
    <div id="carts">
      <ChartContainer
        title="シカゴ連銀小売指数（CARTS）"
        showPeriodSelector={false}
        dataSource="Chicago Fed CARTS"
        sourceUrl="https://www.chicagofed.org/research/data/carts/current-data"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            { label: '名目', value: formatDollarB(latest?.nominal), color: COLORS.nominal },
            { label: '実質', value: formatDollarB(latest?.real), color: COLORS.real },
          ]}
          date={latest?.date}
          nextRelease={data.next_release}
        />

        {/* 時系列チャート */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <AntTooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=carts', '_blank')}
            >
              データ比較
            </Button>
          </AntTooltip>
        </div>
        <ResponsiveContainer width="100%" height={450}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={AXIS_STYLE.tick}
              interval={AXIS_STYLE.interval}
            />
            <YAxis
              tickFormatter={(v) => `$${v}B`}
              tick={AXIS_STYLE.tick}
              domain={['dataMin - 10', 'dataMax + 10']}
            />
            <Tooltip content={<CartsTooltip data={filteredData} />} />
            <Legend
              onClick={(e) => handleLegendClick(e.dataKey as string)}
              wrapperStyle={{ cursor: 'pointer' }}
            />
            <Line
              type="monotone"
              dataKey="nominalB"
              name={SERIES_NAMES.nominal}
              stroke={COLORS.nominal}
              strokeWidth={2}
              dot={false}
              hide={hiddenSeries.has('nominalB')}
              connectNulls={true}
            />
            <Line
              type="monotone"
              dataKey="realB"
              name={SERIES_NAMES.real}
              stroke={COLORS.real}
              strokeWidth={2}
              dot={false}
              hide={hiddenSeries.has('realB')}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
