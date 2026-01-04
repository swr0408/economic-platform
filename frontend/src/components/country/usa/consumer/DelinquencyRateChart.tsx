/**
 * クレジットカードローン延滞率チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { DelinquencyRateData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatQuarterLabel,
  formatQuarterLabelJP,
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

interface DelinquencyRateChartProps {
  data: DelinquencyRateData | null
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function DelinquencyRateChart({ data }: DelinquencyRateChartProps) {
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
    return <LoadingChart title="クレジットカードローン延滞率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="クレジットカードローン延滞率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="delinquency-rate">
      <ChartContainer
        title="クレジットカードローン延滞率"
        showPeriodSelector={false}
        dataSource="Federal Reserve"
        sourceUrl="https://www.federalreserve.gov/releases/chargeoff/default.htm"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={CHART_COLORS.negative}
          date={latest?.date}
          format="percent"
          decimals={2}
          dateFormatter={formatQuarterLabelJP}
        />

        {/* 時系列チャート */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=delinquency_rate', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: CHART_COLORS.negative, name: 'クレジットカードローン延滞率' },
          ]}
          xAxisFormatter={formatQuarterLabel}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          tooltipLabelFormatter={formatQuarterLabelJP}
          tooltipFormatter={createPercentFormatter(2, false)}
          showZeroLine={false}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
