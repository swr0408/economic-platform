/**
 * シカゴ連銀小売指数（CARTS）チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CartsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  usePeriodFiltering,
  formatDateLabel,
  createDollarFormatter,
  useHiddenSeries,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
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

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'nominalB', color: COLORS.nominal, name: '名目値', hide: hiddenSeries.has('nominalB') },
            { dataKey: 'realB', color: COLORS.real, name: '実質値（2017年基準）', hide: hiddenSeries.has('realB') },
          ]}
          yAxisFormatter={(v) => `$${v}B`}
          yDomain={['dataMin - 10', 'dataMax + 10']}
          tooltipLabelFormatter={formatDateLabel}
          tooltipFormatter={createDollarFormatter(1, 1)}
          onLegendClick={handleLegendClick}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
