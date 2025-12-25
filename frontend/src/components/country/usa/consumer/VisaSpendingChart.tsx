/**
 * Visa支出モメンタム指数チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { VisaSpendingData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  createNumberFormatter,
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

interface VisaSpendingChartProps {
  data: VisaSpendingData | null
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function VisaSpendingChart({ data }: VisaSpendingChartProps) {
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
    return <LoadingChart title="Visa支出モメンタム指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Visa支出モメンタム指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="visa-spending">
      <ChartContainer
        title="Visa支出モメンタム指数"
        showPeriodSelector={false}
        dataSource="FRED"
        sourceUrl="https://usa.visa.com/partner-with-us/visa-consulting-analytics/spending-momentum-index.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={CHART_COLORS.primary}
          date={latest?.date}
          dateFormatter={formatDateLabel}
          format="number"
          decimals={1}
          nextRelease={data.next_release}
        />

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: CHART_COLORS.primary, name: 'Visa支出モメンタム指数' },
          ]}
          yDomain={['dataMin - 5', 'dataMax + 5']}
          tooltipLabelFormatter={formatDateLabel}
          tooltipFormatter={createNumberFormatter(1)}
          showZeroLine={false}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
