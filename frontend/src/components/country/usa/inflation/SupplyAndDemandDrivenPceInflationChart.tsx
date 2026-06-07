/**
 * Supply- and Demand-Driven PCE Inflation チャート（PCE需給分解）
 *
 * SF Fed の論文に基づき、コアPCE YoY を 需要起因 / 供給起因 / 判別不能 に分解
 * 3系列の積み上げ棒グラフで表示（合計＝コアPCE YoY）
 *
 * データソース: SF Fed
 * https://www.frbsf.org/research-and-insights/data-and-indicators/supply-and-demand-driven-pce-inflation/
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { SupplyAndDemandDrivenPceInflationData } from '../../../../hooks/useDashboardData'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardBarChart,
} from '../common/ChartComponents'

interface SupplyAndDemandDrivenPceInflationChartProps {
  data: SupplyAndDemandDrivenPceInflationData | null
}

const COLOR_DEMAND = '#ef4444'   // 需要起因（赤）: 需要圧力でインフレを押し上げ
const COLOR_SUPPLY = '#3b82f6'   // 供給起因（青）: 供給制約でインフレを押し上げ
const COLOR_AMBIGUOUS = '#94a3b8' // 判別不能（グレー）
const COLOR_TOTAL = '#a855f7'    // 合計（紫）

export default function SupplyAndDemandDrivenPceInflationChart({
  data,
}: SupplyAndDemandDrivenPceInflationChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const sortedData = useSortedData(data?.data)

  const chartData = useMemo(() => {
    return sortedData.map((item) => ({
      date: item.date,
      demand_driven: item.demand_driven,
      supply_driven: item.supply_driven,
      ambiguous: item.ambiguous,
      total: item.total,
    }))
  }, [sortedData])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2021,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="PCE需給分解（Supply- and Demand-Driven PCE Inflation）" />
  }

  if (!hasData) {
    return (
      <ChartContainer
        title="PCE需給分解（Supply- and Demand-Driven PCE Inflation）"
        showPeriodSelector={false}
        showDataSource={false}
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="supply-and-demand-driven-pce-inflation">
      <ChartContainer
        title="PCE需給分解（Supply- and Demand-Driven PCE Inflation）"
        showPeriodSelector={false}
        dataSource="SF Fed"
        sourceUrl="https://www.frbsf.org/research-and-insights/data-and-indicators/supply-and-demand-driven-pce-inflation/"
      >
        <LatestValueBox
          items={[
            {
              label: '需要起因',
              value: latest?.demand_driven,
              color: COLOR_DEMAND,
              format: 'percent',
            },
            {
              label: '供給起因',
              value: latest?.supply_driven,
              color: COLOR_SUPPLY,
              format: 'percent',
            },
            {
              label: '判別不能',
              value: latest?.ambiguous,
              color: COLOR_AMBIGUOUS,
              format: 'percent',
            },
            {
              label: '合計（コアPCE YoY）',
              value: latest?.total,
              color: COLOR_TOTAL,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          nextRelease={data.next_release}
        />

        <PeriodSelector
          onPeriodChange={setSelectedPeriod}
          selectedPeriod={selectedPeriod}
        />

        <StandardBarChart
          data={filteredData}
          bars={[
            {
              dataKey: 'demand_driven',
              color: COLOR_DEMAND,
              name: '需要起因',
              stackId: 'pce',
              hide: hiddenSeries.has('demand_driven'),
            },
            {
              dataKey: 'supply_driven',
              color: COLOR_SUPPLY,
              name: '供給起因',
              stackId: 'pce',
              hide: hiddenSeries.has('supply_driven'),
            },
            {
              dataKey: 'ambiguous',
              color: COLOR_AMBIGUOUS,
              name: '判別不能',
              stackId: 'pce',
              hide: hiddenSeries.has('ambiguous'),
            },
          ]}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          tooltipValueFormatter={(v) => (v != null ? `${v.toFixed(2)}%` : 'N/A')}
          showZeroLine={true}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
