/**
 * 家計貯蓄率チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PersonalSavingRateData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
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

interface PersonalSavingRateChartProps {
  data: PersonalSavingRateData | null
}

// パーセントフォーマッター（符号なし）
const createPercentNoSignFormatter = (decimals: number = 1) => {
  return (value: unknown, name: string): [string, string] => {
    const numValue = typeof value === 'number' ? value : null
    if (numValue === null) return ['N/A', name]
    return [`${numValue.toFixed(decimals)}%`, name]
  }
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function PersonalSavingRateChart({ data }: PersonalSavingRateChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="家計貯蓄率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="家計貯蓄率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  return (
    <div id="personal-saving-rate">
      <ChartContainer
        title="家計貯蓄率"
        showPeriodSelector={false}
        dataSource="BEA / FRED"
        sourceUrl="https://fred.stlouisfed.org/series/PSAVERT"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={CHART_COLORS.primary}
          date={latest?.date}
          nextRelease={nextRelease}
          format="percent"
          decimals={1}
          dateFormatter={formatDateLabelJP}
        />

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: CHART_COLORS.primary, name: '家計貯蓄率' },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 1', 'dataMax + 1']}
          tooltipLabelFormatter={formatDateLabelJP}
          tooltipFormatter={createPercentNoSignFormatter(1)}
          showZeroLine={false}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
