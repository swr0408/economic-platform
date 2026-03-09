/**
 * 銀行貸し出し態度（SLOOS）チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { BankLendingData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { usePeriodFiltering, formatQuarterLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../common/ChartComponents'

interface BankLendingChartProps {
  data: BankLendingData | null
}

export default function BankLendingChart({ data }: BankLendingChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(20)

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
    defaultStartYear: 2000,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="銀行貸し出し態度（SLOOS）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="銀行貸し出し態度（SLOOS）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatPercentage = (value: number) => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(1)}%`
  }

  return (
    <div id="bank-lending-chart">
      <ChartContainer
        title="銀行貸し出し態度"
        showPeriodSelector={false}
        dataSource="FRED (Federal Reserve)"
        sourceUrl="https://www.federalreserve.gov/data/sloos.htm"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={data.latest?.value}
          valueColor="#b70303"
          date={data.latest?.date}
          format="percent"
          decimals={1}
          dateFormatter={formatQuarterLabel}
        />

        {/* 期間セレクタ + 比較ボタン（横並び） */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=bank_lending', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color="#b70303"
          name="銀行貸し出し態度"
          height={450}
          tickFormatter={formatPercentage}
          tooltipFormatter={formatPercentage}
          tooltipLabelFormatter={formatQuarterLabel}
          xAxisTickFormatter={formatQuarterLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
        />
      </ChartContainer>
    </div>
  )
}
