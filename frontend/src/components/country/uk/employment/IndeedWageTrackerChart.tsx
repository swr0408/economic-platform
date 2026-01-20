/**
 * UK Indeed賃金トラッカーチャートコンポーネント
 *
 * データ:
 * - Posted Wage Growth YoY (求人賃金成長率 前年比)
 * - 3ヶ月移動平均
 *
 * データソース:
 * - Indeed Hiring Lab (GitHub)
 *
 * 発表スケジュール:
 * - 毎月15日以降に更新
 */
import { useState, useMemo, useCallback } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { IndeedWageTrackerUKData } from '../../../../hooks/useDashboardData'
import type { PeriodType } from '../../usa/common/useChartData'

interface IndeedWageTrackerChartProps {
  data: IndeedWageTrackerUKData | null
}

interface ChartDataPoint {
  date: string
  value: number
  ma3: number | null
  [key: string]: unknown
}

// グラフの色
const YOY_COLOR = '#f39c12'
const MA3_COLOR = '#27ae60'

export default function IndeedWageTrackerChart({ data }: IndeedWageTrackerChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter(point => point.value !== null)
      .map(point => ({
        date: point.date,
        value: point.value as number,
        ma3: point.ma3,
      }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 期間変更ハンドラ
  const handlePeriodChange = useCallback((period: PeriodType) => {
    setSelectedPeriod(period)
  }, [])

  // データ比較ページを開く
  const handleCompare = useCallback(() => {
    window.open('/compare?s=uk_indeed_wage_tracker&s=uk_wages_total', '_blank')
  }, [])

  if (data === null) {
    return <LoadingChart title="Indeed賃金トラッカー" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Indeed賃金トラッカー" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="uk-indeed-wage-tracker-chart">
      <ChartContainer
        title="Indeed賃金トラッカー"
        showPeriodSelector={false}
        dataSource="Indeed Hiring Lab"
        sourceUrl="https://www.hiringlab.org/jp/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={YOY_COLOR}
          date={latest?.date}
          format="percent"
          decimals={2}
        />

        {/* 期間セレクター */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={handlePeriodChange} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={handleCompare}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート表示 */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'value',
              color: YOY_COLOR,
              name: 'Indeed賃金トラッカー',
              hide: hiddenSeries.has('value')
            },
            {
              dataKey: 'ma3',
              color: MA3_COLOR,
              name: '3ヶ月移動平均',
              hide: hiddenSeries.has('ma3')
            },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
          onLegendClick={handleLegendClick}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
        />
      </ChartContainer>
    </div>
  )
}
