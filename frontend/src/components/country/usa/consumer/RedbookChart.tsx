/**
 * Redbook小売売上高指数チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { RedbookData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelFull,
  createPercentFormatter,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface RedbookChartProps {
  data: RedbookData | null
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function RedbookChart({ data }: RedbookChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="Redbook小売売上高指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Redbook小売売上高指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="redbook">
      <ChartContainer
        title="レッドブック（前年比）"
        showPeriodSelector={false}
        dataSource="Redbook Research"
        sourceUrl="https://www.redbookresearch.com/"
      >
        {/* 最新値表示 */}
        {latest && (
          <SimpleLatestValueBox
            label="最新値"
            value={latest.value}
            valueColor={latest.value >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative}
            date={latest.date}
            dateFormatter={formatDateLabelFull}
            format="percent"
            decimals={1}
            nextRelease={data.next_release}
          />
        )}

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: CHART_COLORS.primary, name: 'レッドブック（前年比）' },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 2', 'dataMax + 2']}
          tooltipLabelFormatter={formatDateLabelFull}
          tooltipFormatter={createPercentFormatter(2)}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
