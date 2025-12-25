/**
 * Affinityカード支出チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { AffinitySpendData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  TOOLTIP_STYLE,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  createPercentFormatter,
  type PeriodType,
} from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox, ZERO_LINE_PROPS } from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface AffinitySpendChartProps {
  data: AffinitySpendData | null
}

// カラー設定
const COLOR = '#2f54eb'

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AffinitySpendChart({ data }: AffinitySpendChartProps) {
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
    return <LoadingChart title="Affinityカード支出" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Affinityカード支出" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="affinity-spend">
      <ChartContainer
        title="クレジット / デビットカードカード支出"
        showPeriodSelector={false}
        dataSource="Opportunity Insights Economic Tracker"
        sourceUrl="https://economictracker.org/"
      >
        {/* 最新値表示 */}
        {latest && (
          <SimpleLatestValueBox
            label="2020年1月比"
            value={latest.value}
            valueColor={COLOR}
            date={latest.date}
            format="percent"
            decimals={1}
          />
        )}

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <ResponsiveContainer width="100%" height={450}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis dataKey="date" tickFormatter={formatDateLabel} tick={AXIS_STYLE.tick} interval={AXIS_STYLE.interval} />
            <YAxis domain={['dataMin - 5', 'dataMax + 5']} tick={AXIS_STYLE.tick} tickFormatter={(v) => `${v}%`} />
            <Tooltip
              labelFormatter={formatDateLabel}
              formatter={createPercentFormatter(1)}
              contentStyle={TOOLTIP_STYLE}
            />
            <ReferenceLine {...ZERO_LINE_PROPS} />
            <Line type="monotone" dataKey="value" name="クレジット / デビットカードカード支出" stroke={COLOR} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={true} />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
