import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { ISMManufacturingData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../common/ChartComponents'

interface ISMManufacturingChartProps {
  data: ISMManufacturingData | null
}

export default function ISMManufacturingChart({ data }: ISMManufacturingChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // データを日付昇順にソートしてDataPoint型に変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="ISM製造業景況指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ISM製造業景況指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatValue = (value: number) => {
    return value.toFixed(1)
  }

  // グラフの色
  const CHART_COLOR = '#1890ff' // 青

  return (
    <div id="ism-manufacturing-chart">
      <ChartContainer
        title="ISM製造業景況指数"
        showPeriodSelector={false}
        dataSource="ISM"
        sourceUrl="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={data.latest?.value}
          valueColor={CHART_COLOR}
          date={data.latest?.date}
          nextRelease={data.next_release}
          format="number"
          decimals={1}
        />

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLOR}
          name="ISM製造業景況指数"
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={formatValue}
          tooltipLabelFormatter={formatDateLabel}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={true}
          fiftyLineValue={50}
          connectNulls={true}
          hideLegend={true}
        />
      </ChartContainer>
    </div>
  )
}
