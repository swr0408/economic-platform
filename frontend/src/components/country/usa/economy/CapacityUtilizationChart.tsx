import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CapacityUtilizationData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../common/ChartComponents'

interface CapacityUtilizationChartProps {
  data: CapacityUtilizationData | null
}

export default function CapacityUtilizationChart({ data }: CapacityUtilizationChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="設備稼働率（Capacity Utilization）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="設備稼働率（Capacity Utilization）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値
  const latest = data.latest

  const formatValue = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A'
    return `${value.toFixed(1)}%`
  }

  return (
    <div id="capacity-utilization-chart">
      <ChartContainer
        title="設備稼働率"
        showPeriodSelector={false}
        dataSource="FRED (FRB)"
        sourceUrl="https://www.federalreserve.gov/releases/G17/default.htm"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor="#1890ff"
          date={latest?.date}
          nextRelease={data.next_release}
          format="percent"
          decimals={1}
        />

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color="#1890ff"
          name="設備稼働率"
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={formatValue}
          tooltipLabelFormatter={formatDateLabel}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
        />
      </ChartContainer>
    </div>
  )
}
